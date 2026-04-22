import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.main as api_main
import src.patient_report_context as report_context
import src.trustmed_brain as trustmed_brain


MINIMAL_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE"
    "0000000C49444154789C6360000000020001E221BC330000000049454E44AE426082"
)
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


class PatientAttachmentApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_dirs = {
            "UPLOADS_DIR": api_main.UPLOADS_DIR,
            "PATIENT_FILES_DIR": api_main.PATIENT_FILES_DIR,
            "STORAGE_DIR": api_main.STORAGE_DIR,
            "PATIENT_FILES_REGISTRY": api_main.PATIENT_FILES_REGISTRY,
        }
        self.original_report_dirs = {
            "UPLOADS_DIR": report_context.UPLOADS_DIR,
            "STORAGE_DIR": report_context.STORAGE_DIR,
            "PATIENT_FILES_REGISTRY": report_context.PATIENT_FILES_REGISTRY,
        }

        api_main.UPLOADS_DIR = os.path.join(self.tempdir.name, "uploads")
        api_main.PATIENT_FILES_DIR = os.path.join(api_main.UPLOADS_DIR, "patient-files")
        api_main.STORAGE_DIR = os.path.join(self.tempdir.name, "storage")
        api_main.PATIENT_FILES_REGISTRY = os.path.join(api_main.STORAGE_DIR, "patient_files.json")
        report_context.UPLOADS_DIR = api_main.UPLOADS_DIR
        report_context.STORAGE_DIR = api_main.STORAGE_DIR
        report_context.PATIENT_FILES_REGISTRY = api_main.PATIENT_FILES_REGISTRY
        api_main._ensure_dirs()

        self.client = TestClient(api_main.app)

    def tearDown(self):
        api_main.UPLOADS_DIR = self.original_dirs["UPLOADS_DIR"]
        api_main.PATIENT_FILES_DIR = self.original_dirs["PATIENT_FILES_DIR"]
        api_main.STORAGE_DIR = self.original_dirs["STORAGE_DIR"]
        api_main.PATIENT_FILES_REGISTRY = self.original_dirs["PATIENT_FILES_REGISTRY"]
        report_context.UPLOADS_DIR = self.original_report_dirs["UPLOADS_DIR"]
        report_context.STORAGE_DIR = self.original_report_dirs["STORAGE_DIR"]
        report_context.PATIENT_FILES_REGISTRY = self.original_report_dirs["PATIENT_FILES_REGISTRY"]
        self.tempdir.cleanup()

    def _upload_pdf_with_text(self, text, patient_id="10002428", fallback_text=None):
        patches = [
            patch.object(report_context, "_extract_pdf_text", return_value=text),
        ]
        if fallback_text is not None:
            patches.append(patch.object(report_context, "_transcribe_pdf_with_vision", return_value=fallback_text))

        with patches[0]:
            if len(patches) > 1:
                with patches[1]:
                    response = self.client.post(
                        f"/patient/{patient_id}/attachments",
                        files={"file": ("radiology-report.pdf", MINIMAL_PDF, "application/pdf")},
                    )
            else:
                response = self.client.post(
                    f"/patient/{patient_id}/attachments",
                    files={"file": ("radiology-report.pdf", MINIMAL_PDF, "application/pdf")},
                )
        return response

    def test_patient_png_upload_succeeds(self):
        response = self.client.post(
            "/patient/10002428/attachments",
            files={"file": ("chest-xray.png", MINIMAL_PNG, "image/png")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["patient_id"], "10002428")
        self.assertEqual(data["uploaded_by"], "patient")
        self.assertEqual(data["file_kind"], "image")
        self.assertTrue(data["url"].startswith("/uploads/patient-files/10002428/"))
        self.assertTrue(os.path.exists(api_main._attachment_path_from_url(data["url"])))

    def test_patient_pdf_upload_succeeds(self):
        response = self._upload_pdf_with_text(
            "Report Date: 2026-04-20\nFindings: Improving pneumonia.\nBlood pressure: 132/78\nSpO2: 97%\nMedication: Lisinopril 10 mg"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["uploaded_by"], "patient")
        self.assertEqual(data["file_kind"], "pdf")
        self.assertEqual(data["mime_type"], "application/pdf")
        self.assertEqual(data["processing_status"], "completed")
        self.assertTrue(data["summary_preview"])

        sidecar_path = report_context.attachment_sidecar_path(api_main._attachment_path_from_url(data["url"]))
        self.assertTrue(os.path.exists(sidecar_path))

    def test_patient_pdf_upload_uses_fallback_when_text_is_thin(self):
        response = self._upload_pdf_with_text(
            "thin",
            fallback_text="Findings: Pleural effusion.\nBlood pressure: 150/80\nSpO2: 95%\nMedication: Furosemide 20 mg"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["processing_status"], "completed_with_fallback")
        self.assertTrue(data["summary_preview"])

    def test_lab_report_summary_ignores_header_boilerplate(self):
        report_text = """Name : DUMMY
Page 1 of 2
Classification: Restricted
Lab No.
Comments
Mycoplasma pneumoniae accounts for nearly 20% of all cases of pneumonia.
Negative IgG/IgM result does not rule out the presence of Mycoplasma pneumonia associated disease.
MYCOPLASMA PNEUMONIAE ANTIBODIES IgG & IgM, SERUM
M.pneumoniae IgG
12.00
M.pneumoniae IgM
10.00
"""
        response = self._upload_pdf_with_text(report_text)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Mycoplasma pneumoniae", data["summary_preview"])
        self.assertNotIn("Name : DUMMY", data["summary_preview"])

    def test_unsupported_upload_returns_400(self):
        response = self.client.post(
            "/patient/10002428/attachments",
            files={"file": ("notes.txt", b"not supported", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Only image files and PDF reports are supported", response.json()["detail"])

    def test_clinician_link_requires_uploads_path(self):
        external_path = os.path.join(self.tempdir.name, "outside.png")
        with open(external_path, "wb") as f:
            f.write(MINIMAL_PNG)

        response = self.client.post(
            "/patient/10002428/attachments/link-clinician-upload",
            json={"image_path": external_path, "title": "outside.png"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("uploads directory", response.json()["detail"])

    def test_attachment_list_is_newest_first_and_patient_scoped(self):
        upload_path = os.path.join(api_main.UPLOADS_DIR, "clinician-scan.png")
        with open(upload_path, "wb") as f:
            f.write(MINIMAL_PNG)

        first = self.client.post(
            "/patient/10002428/attachments/link-clinician-upload",
            json={"image_path": upload_path, "title": "baseline-scan.png"},
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/patient/10002428/attachments",
            files={"file": ("follow-up-report.pdf", MINIMAL_PDF, "application/pdf")},
        )
        self.assertEqual(second.status_code, 200)

        other_patient = self.client.post(
            "/patient/99999999/attachments",
            files={"file": ("other-patient.pdf", MINIMAL_PDF, "application/pdf")},
        )
        self.assertEqual(other_patient.status_code, 200)

        response = self.client.get("/patient/10002428/attachments")
        self.assertEqual(response.status_code, 200)

        attachments = response.json()["attachments"]
        self.assertEqual(len(attachments), 2)
        self.assertEqual(attachments[0]["title"], "follow up report")
        self.assertEqual(attachments[0]["uploaded_by"], "patient")
        self.assertEqual(attachments[1]["title"], "baseline scan")
        self.assertTrue(all(item["patient_id"] == "10002428" for item in attachments))

    def test_patient_endpoint_merges_report_vitals_into_history(self):
        response = self._upload_pdf_with_text(
            "Report Date: 2026-04-21\nFindings: Mild pleural effusion.\nBlood pressure: 150/80\nHeart rate: 88\nSpO2: 96%\nTemperature: 98.7 F"
        )
        self.assertEqual(response.status_code, 200)

        patient_response = self.client.get("/patient/10002428")
        self.assertEqual(patient_response.status_code, 200)
        data = patient_response.json()

        self.assertEqual(data["vitals"]["source"], "report")
        self.assertEqual(data["vitals"]["systolic_bp"], 150)
        self.assertEqual(data["vitals_history"][-1]["source"], "report")
        self.assertTrue(any(item.get("source") == "chart" for item in data["vitals_history"]))
        self.assertTrue(data["report_summaries"])

    def test_patient_summary_endpoint_does_not_404_when_report_has_extraction_error_field(self):
        response = self._upload_pdf_with_text(
            "Report Date: 2026-04-21\nFindings: Right lower lobe opacity.\nBlood pressure: 144/82\nSpO2: 95%"
        )
        self.assertEqual(response.status_code, 200)

        async def fake_summary_response(prompt, model=None):
            return "We could not generate a detailed summary right now."

        with patch.object(api_main, "ask_trustmed_direct", fake_summary_response):
            summary_response = self.client.post("/patient/10002428/summary")

        self.assertEqual(summary_response.status_code, 200)
        payload = summary_response.json()
        self.assertIn("summary", payload)
        self.assertTrue(payload["summary"])

    def test_clinician_chat_stream_receives_patient_id_and_report_context(self):
        upload_response = self._upload_pdf_with_text(
            "Report Date: 2026-04-21\nDiagnoses: Pneumonia\nFindings: Right lower lobe opacity.\nMedication: Lisinopril 10 mg\nBlood pressure: 144/82"
        )
        self.assertEqual(upload_response.status_code, 200)

        captured = {}

        async def fake_stream(query, history, temperature=None, model=None, vision_model=None, patient_id=None, report_context=""):
            captured["query"] = query
            captured["patient_id"] = patient_id
            captured["report_context"] = report_context
            yield {"type": "done", "final_response": "ok"}

        with patch.object(api_main, "ask_trustmed_streaming", fake_stream):
            response = self.client.post(
                "/chat/stream",
                json={
                    "message": "check the reports of the patient",
                    "session_id": "test-session",
                    "patient_id": "10002428",
                    "assistant_mode": "clinician",
                    "persist": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["patient_id"], "10002428")
        self.assertIn("Uploaded report context", captured["report_context"])
        self.assertIn("Pneumonia", captured["report_context"])

    def test_patient_report_question_skips_heavy_retrieval(self):
        report_digest = (
            "Uploaded report context (most recent first):\n"
            "- Z677 (2022-08-11T00:00:00)\n"
            "  Summary: Mycoplasma pneumoniae accounts for nearly 20% of all cases of pneumonia.\n"
        )

        class FakeLLM:
            def __init__(self, *args, **kwargs):
                pass

            def stream(self, prompt):
                yield SimpleNamespace(content="Your latest report suggests atypical pneumonia.")

        async def collect_events():
            events = []
            async for event in trustmed_brain.ask_trustmed_streaming(
                query=(
                    "[PATIENT PORTAL] You are TrustMed AI's patient visit assistant.\n\n"
                    'Patient question: "check the report"\n\n'
                    "Explain in plain language."
                ),
                patient_id="10002428",
                report_context=report_digest,
            ):
                events.append(event)
            return events

        with patch.object(trustmed_brain, "get_patient_context", return_value="Patient 10002428"), \
             patch.object(trustmed_brain, "get_graph_context", side_effect=AssertionError("graph lookup should be skipped")), \
             patch.object(trustmed_brain, "get_vector_context_fast", side_effect=AssertionError("vector lookup should be skipped")), \
             patch.object(trustmed_brain, "check_drug_interactions", side_effect=AssertionError("drug checker should be skipped")), \
             patch.object(trustmed_brain, "ChatOpenAI", FakeLLM):
            events = asyncio.run(collect_events())

        self.assertTrue(any(event.get("step") == "search" and "latest uploaded report" in event.get("message", "") for event in events))
        self.assertTrue(any(event.get("type") == "token" for event in events))
        self.assertEqual(events[-1]["type"], "done")

    def test_patient_stream_timeout_uses_direct_completion_fallback(self):
        report_digest = (
            "Uploaded report context (most recent first):\n"
            "- Z677 (2022-08-11T00:00:00)\n"
            "  Summary: Mycoplasma pneumoniae accounts for nearly 20% of all cases of pneumonia.\n"
        )

        async def fake_timeout_stream(*args, **kwargs):
            if False:
                yield ""
            raise asyncio.TimeoutError()

        class FakeLLM:
            def __init__(self, *args, **kwargs):
                pass

            def stream(self, prompt):
                return iter(())

        async def collect_events():
            events = []
            async for event in trustmed_brain.ask_trustmed_streaming(
                query=(
                    "[PATIENT PORTAL] You are TrustMed AI's patient visit assistant.\n\n"
                    'Patient question: "check the report"\n\n'
                    "Explain in plain language."
                ),
                patient_id="10002428",
                report_context=report_digest,
            ):
                events.append(event)
            return events

        with patch.object(trustmed_brain, "get_patient_context", return_value="Patient 10002428"), \
             patch.object(trustmed_brain, "ChatOpenAI", FakeLLM), \
             patch.object(trustmed_brain, "ask_trustmed_direct", return_value="Direct Gemini fallback answer."), \
             patch.object(trustmed_brain, "_stream_sync_tokens", fake_timeout_stream):
            events = asyncio.run(collect_events())

        replace_events = [event for event in events if event.get("type") == "replace"]
        self.assertTrue(replace_events)
        self.assertEqual(replace_events[-1]["content"], "Direct Gemini fallback answer.")
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["final_response"], "Direct Gemini fallback answer.")

    def test_patient_stream_timeout_falls_back_to_report_summary_when_direct_completion_fails(self):
        report_digest = (
            "Uploaded report context (most recent first):\n"
            "- Z677 (2022-08-11T00:00:00)\n"
            "  Summary: Mycoplasma pneumoniae accounts for nearly 20% of all cases of pneumonia.\n"
        )

        async def fake_timeout_stream(*args, **kwargs):
            if False:
                yield ""
            raise asyncio.TimeoutError()

        class FakeLLM:
            def __init__(self, *args, **kwargs):
                pass

            def stream(self, prompt):
                return iter(())

        async def collect_events():
            events = []
            async for event in trustmed_brain.ask_trustmed_streaming(
                query=(
                    "[PATIENT PORTAL] You are TrustMed AI's patient visit assistant.\n\n"
                    'Patient question: "what does my latest report suggest"\n\n'
                    "Explain in plain language."
                ),
                patient_id="10002428",
                report_context=report_digest,
            ):
                events.append(event)
            return events

        with patch.object(trustmed_brain, "get_patient_context", return_value="Patient 10002428"), \
             patch.object(trustmed_brain, "ChatOpenAI", FakeLLM), \
             patch.object(trustmed_brain, "ask_trustmed_direct", return_value="Explanation unavailable. Please consult your physician."), \
             patch.object(trustmed_brain, "_stream_sync_tokens", fake_timeout_stream):
            events = asyncio.run(collect_events())

        replace_events = [event for event in events if event.get("type") == "replace"]
        self.assertTrue(replace_events)
        self.assertIn("Your latest uploaded report suggests:", replace_events[-1]["content"])
        self.assertEqual(events[-1]["type"], "done")
        self.assertIn("Mycoplasma pneumoniae", events[-1]["final_response"])

    def test_patient_drug_checker_uses_chart_context_only(self):
        captured = {}

        class FakeLLM:
            def __init__(self, *args, **kwargs):
                pass

            def stream(self, prompt):
                yield SimpleNamespace(content="ok")

        def fake_drug_checker(context):
            captured["context"] = context
            return ""

        async def collect_events():
            events = []
            async for event in trustmed_brain.ask_trustmed_streaming(
                query=(
                    "[PATIENT PORTAL] You are TrustMed AI's patient visit assistant.\n\n"
                    'Patient question: "what should I know about my medicines?"\n\n'
                    "Explain in plain language."
                ),
                patient_id="10002428",
                report_context=(
                    "Uploaded report context (most recent first):\n"
                    "- Z677 (2022-08-11T00:00:00)\n"
                    "  Summary: Mycoplasma pneumoniae accounts for nearly 20% of all cases of pneumonia.\n"
                ),
            ):
                events.append(event)
            return events

        with patch.object(trustmed_brain, "get_patient_context", return_value="Current Medications: lisinopril, albuterol"), \
             patch.object(trustmed_brain, "get_graph_context", return_value="No structured data found."), \
             patch.object(trustmed_brain, "get_vector_context_fast", return_value="No relevant literature found."), \
             patch.object(trustmed_brain, "check_drug_interactions", side_effect=fake_drug_checker), \
             patch.object(trustmed_brain, "ChatOpenAI", FakeLLM):
            events = asyncio.run(collect_events())

        self.assertEqual(captured["context"], "Current Medications: lisinopril, albuterol")
        self.assertEqual(events[-1]["type"], "done")


if __name__ == "__main__":
    unittest.main()
