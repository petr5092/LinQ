import logging
import os
import tempfile
import unittest
from logging.handlers import RotatingFileHandler

from app.logging_config import LOG_BACKUPS, MAX_LOG_BYTES, configure_logging, shutdown_logging


class ApplicationLoggingTest(unittest.TestCase):
    def test_writes_utf8_log_and_configures_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "linq.log")
            logger = configure_logging(path)
            try:
                logger.info("service_ready")
                for handler in logger.handlers:
                    handler.flush()

                with open(path, encoding="utf-8") as log_file:
                    content = log_file.read()
                self.assertIn("INFO linq: service_ready", content)

                file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
                self.assertEqual(len(file_handlers), 1)
                self.assertEqual(file_handlers[0].maxBytes, MAX_LOG_BYTES)
                self.assertEqual(file_handlers[0].backupCount, LOG_BACKUPS)
            finally:
                shutdown_logging()


if __name__ == "__main__":
    unittest.main()
