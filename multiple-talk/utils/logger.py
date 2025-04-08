import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name, log_file='app.log', level=logging.INFO):
    """配置并返回一个logger实例"""
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger