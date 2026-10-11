from concurrent import futures
import grpc
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging(settings.log_level)
logger = get_logger(__name__)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # TODO: register SchemaInferenceServicer here once proto stubs are generated
    server.add_insecure_port("[::]:50051")
    server.start()
    logger.info("intelligence_grpc_server_started", port=50051)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
