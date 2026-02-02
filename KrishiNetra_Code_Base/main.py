# main.py

import logging
import threading
import sys
from os.path import dirname, abspath

PROJECT_ROOT = dirname(abspath(__file__))
sys.path.append(PROJECT_ROOT)

from services.data_logger import setup_logging
from core.robot_controller import RobotController
from web_interface.app import create_app
import config

setup_logging()
logger = logging.getLogger(__name__)


def run_robot_controller(controller: RobotController):
    logger.info("Robot controller thread started.")
    try:
        controller.run()
    except Exception as e:
        logger.critical(f"Robot controller crash: {e}", exc_info=True)
    finally:
        logger.info("Robot controller thread ended.")


def run_flask_app(app, host, port):
    logger.info(f"Web server starting at http://{host}:{port}")

    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        logger.warning("Waitress not installed. Using Flask dev server.")
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.critical(f"Flask thread crash: {e}", exc_info=True)
    finally:
        logger.info("Web server thread ended.")


def main():
    logger.info("==============================================")
    logger.info(f"   STARTING {config.PROJECT_NAME.upper()} SYSTEM")
    logger.info("==============================================")

    controller = RobotController()

    if not controller.is_initialized:
        logger.critical("Critical init failure. Aborting.")
        return

    flask_app = create_app(controller)

    robot_thread = threading.Thread(
        target=run_robot_controller,
        args=(controller,),
        name="RobotControllerThread"
    )

    web_thread = threading.Thread(
        target=run_flask_app,
        args=(flask_app, config.WEB_SERVER_HOST, config.WEB_SERVER_PORT),
        daemon=True,
        name="WebServerThread"
    )

    try:
        robot_thread.start()
        web_thread.start()

        robot_thread.join()

    except KeyboardInterrupt:
        logger.info("CTRL+C received. Shutting down…")

    finally:
        if controller.context.is_running():
            controller.shutdown()

        logger.info("==============================================")
        logger.info(f"   {config.PROJECT_NAME.upper()} SYSTEM OFF")
        logger.info("==============================================")


if __name__ == "__main__":
    main()
