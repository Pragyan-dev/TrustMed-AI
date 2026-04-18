from __future__ import annotations

import os
import ssl


def configure_ssl_certificates() -> str | None:
    """Point Python networking libraries at certifi when no CA bundle is configured."""
    cert_path = os.getenv("SSL_CERT_FILE")
    if not cert_path:
        try:
            import certifi
        except ImportError:
            return None

        cert_path = certifi.where()
        if not cert_path:
            return None
        os.environ.setdefault("SSL_CERT_FILE", cert_path)

    os.environ.setdefault("REQUESTS_CA_BUNDLE", cert_path)
    os.environ.setdefault("CURL_CA_BUNDLE", cert_path)
    return cert_path


def get_ssl_cert_path() -> str | None:
    """Return the configured CA bundle path, bootstrapping from certifi if needed."""
    return configure_ssl_certificates()


def get_ssl_context() -> ssl.SSLContext | None:
    """Build an SSL context that trusts the configured CA bundle."""
    cert_path = configure_ssl_certificates()
    if not cert_path:
        return None
    return ssl.create_default_context(cafile=cert_path)
