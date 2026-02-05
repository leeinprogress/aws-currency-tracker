from app.infrastructure.logging.logger import get_logger, setup_logging


def test_logger_basic_setup():
    setup_logging(level="INFO")
    logger = get_logger("test_logger")
    
    assert logger is not None
    logger.info("test_message", test_key="test_value")


def test_logger_with_extra_fields():
    setup_logging(level="INFO")
    logger = get_logger(__name__)
    
    logger.info(
        "operation_completed",
        operation="create_alert",
        alert_id="alert-123",
        duration_ms=45.2,
    )


def test_logger_different_levels():
    setup_logging(level="DEBUG")
    logger = get_logger(__name__)
    
    logger.debug("debug_message")
    logger.info("info_message")
    logger.warning("warning_message")


def test_logger_exception_handling():
    setup_logging(level="ERROR")
    logger = get_logger(__name__)
    
    try:
        raise ValueError("Test exception")
    except ValueError:
        logger.error("error_occurred", exc_info=True)


def test_logger_with_multiple_fields():
    setup_logging(level="INFO")
    logger = get_logger(__name__)
    
    logger.info(
        "user_action",
        user_id="user-123",
        action="login",
        ip_address="192.168.1.1",
        success=True,
    )
