import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import api.main as api_main


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

        api_main.UPLOADS_DIR = os.path.join(self.tempdir.name, "uploads")
        api_main.PATIENT_FILES_DIR = os.path.join(api_main.UPLOADS_DIR, "patient-files")
        api_main.STORAGE_DIR = os.path.join(self.tempdir.name, "storage")
        api_main.PATIENT_FILES_REGISTRY = os.path.join(api_main.STORAGE_DIR, "patient_files.json")
        api_main._ensure_dirs()

        self.client = TestClient(api_main.app)

    def tearDown(self):
        api_main.UPLOADS_DIR = self.original_dirs["UPLOADS_DIR"]
        api_main.PATIENT_FILES_DIR = self.original_dirs["PATIENT_FILES_DIR"]
        api_main.STORAGE_DIR = self.original_dirs["STORAGE_DIR"]
        api_main.PATIENT_FILES_REGISTRY = self.original_dirs["PATIENT_FILES_REGISTRY"]
        self.tempdir.cleanup()

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
        response = self.client.post(
            "/patient/10002428/attachments",
            files={"file": ("radiology-report.pdf", MINIMAL_PDF, "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["uploaded_by"], "patient")
        self.assertEqual(data["file_kind"], "pdf")
        self.assertEqual(data["mime_type"], "application/pdf")

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


if __name__ == "__main__":
    unittest.main()
