"""
Logging configuration for resume processing
Creates detailed logs with inputs/outputs at each step
"""
import logging
import os
from datetime import datetime
from pathlib import Path

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

def setup_detailed_logging(request_id: str = None):
    """
    Set up detailed logging for a resume processing request
    
    Creates two log files:
    1. Full debug log with all details
    2. Readable summary log with inputs/outputs
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    request_suffix = f"_{request_id}" if request_id else ""
    
    # Full debug log
    debug_log_file = LOGS_DIR / f"debug_{timestamp}{request_suffix}.log"
    
    # Readable summary log
    summary_log_file = LOGS_DIR / f"summary_{timestamp}{request_suffix}.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Debug file handler (everything)
    debug_handler = logging.FileHandler(debug_log_file, mode='w', encoding='utf-8')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(debug_handler)
    
    # Summary file handler (INFO and above)
    summary_handler = logging.FileHandler(summary_log_file, mode='w', encoding='utf-8')
    summary_handler.setLevel(logging.INFO)
    summary_handler.setFormatter(simple_formatter)
    root_logger.addHandler(summary_handler)
    
    # Console handler (WARNING and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    return str(debug_log_file), str(summary_log_file)


def log_section_header(logger, title: str):
    """Log a formatted section header"""
    separator = "=" * 80
    logger.info("")
    logger.info(separator)
    logger.info(f"  {title}")
    logger.info(separator)


def log_subsection(logger, title: str):
    """Log a formatted subsection header"""
    logger.info("")
    logger.info(f"--- {title} ---")


def log_data(logger, label: str, data: any, max_length: int = 500):
    """Log data with label in readable format"""
    import json
    
    if isinstance(data, (dict, list)):
        try:
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            if len(formatted) > max_length:
                formatted = formatted[:max_length] + "... (truncated)"
            logger.info(f"{label}:\n{formatted}")
        except:
            logger.info(f"{label}: {str(data)[:max_length]}")
    elif isinstance(data, str):
        if len(data) > max_length:
            logger.info(f"{label}: {data[:max_length]}... (truncated)")
        else:
            logger.info(f"{label}: {data}")
    else:
        logger.info(f"{label}: {data}")


def log_comparison(logger, label: str, input_data: any, output_data: any, max_length: int = 200):
    """Log input vs output comparison"""
    import json
    
    logger.info(f"\n📊 {label} COMPARISON:")
    logger.info("-" * 40)
    
    if isinstance(input_data, (dict, list)):
        input_str = json.dumps(input_data, ensure_ascii=False)
        output_str = json.dumps(output_data, ensure_ascii=False)
    else:
        input_str = str(input_data)
        output_str = str(output_data)
    
    if len(input_str) > max_length:
        input_str = input_str[:max_length] + "..."
    if len(output_str) > max_length:
        output_str = output_str[:max_length] + "..."
    
    logger.info(f"INPUT:  {input_str}")
    logger.info(f"OUTPUT: {output_str}")
    
    if input_data == output_data:
        logger.info("✅ UNCHANGED (as expected)")
    else:
        logger.info("⚠️  MODIFIED")
    logger.info("-" * 40)
