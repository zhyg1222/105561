from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_PROVIDER: TracerProvider | None = None
_EXPORTER_CONFIGURED = False


def configure_observability(settings, exporter=None, app=None, *, force_exporter: bool = False):
    global _PROVIDER, _EXPORTER_CONFIGURED

    if _PROVIDER is None:
        current = trace.get_tracer_provider()
        if isinstance(current, TracerProvider):
            _PROVIDER = current
        else:
            _PROVIDER = TracerProvider(resource=Resource.create({"service.name": "xiaojuju-agent"}))
            trace.set_tracer_provider(_PROVIDER)
    set_global_textmap(TraceContextTextMapPropagator())

    if exporter is None and settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    if exporter is not None and (force_exporter or not _EXPORTER_CONFIGURED):
        _PROVIDER.add_span_processor(BatchSpanProcessor(exporter))
        _EXPORTER_CONFIGURED = True
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)
    return _PROVIDER
