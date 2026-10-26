"""OpenTelemetry setup. Exports to Application Insights when a connection string is set.

Spans carry counts and verdicts (hits, quarantined chunks, refusal reason), never the
question or the answer, so traces do not become a second copy of sensitive content.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)
SERVICE_NAME = "enterprise-rag-api"


def configure_telemetry(app: FastAPI) -> str:
    """Return the exporter in use: ``azure-monitor`` or ``none``."""
    exporter = "none"
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ImportError:  # pragma: no cover - optional extra
            logger.warning("install the 'monitor' extra to export to Application Insights")
        else:  # pragma: no cover - needs a real connection string
            configure_azure_monitor()
            exporter = "azure-monitor"
    if exporter == "none" and not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(
            TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
        )
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz")
    return exporter
