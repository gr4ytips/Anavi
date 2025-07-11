# data_management/qss_parser.py
# -*- coding: utf-8 -*-
import re
import json
import logging
from PyQt5.QtGui import QColor

logger = logging.getLogger(__name__)

class QSSParser:
    """
    A simplified and robust utility to parse QSS variables from a string.
    """

    @staticmethod
    def parse_variables(variable_content):
        """
        Parses key-value pairs from a string containing variable definitions.
        """
        variables = {}
        # This single, robust regex finds all key-value pairs.
        # It matches '--key: value;' or 'key: value;'
        pattern = re.compile(r'^\s*(?:--)?([\w-]+):\s*([^;]+);', re.MULTILINE)

        for match in pattern.finditer(variable_content):
            key = match.group(1).strip().replace('-', '_')
            raw_value = match.group(2).strip()
            variables[key] = QSSParser._process_value(raw_value)
            logger.debug(f"  Parsed: '{key}' = '{variables[key]}'")

        return variables

    @staticmethod
    def _process_value(value_str):
        """Processes a string value, converting it to the correct type."""
        value_str = value_str.strip().strip("'\"")

        if value_str.startswith('#'):
            return QColor(value_str)
        elif value_str.startswith('rgba'):
            try:
                parts = [p.strip() for p in re.findall(r'[\d\.]+', value_str)]
                if len(parts) == 4:
                    # FIX: Correctly handle both float and int alpha values
                    alpha = float(parts[3])
                    if alpha <= 1.0: # Assumes float alpha (0.0-1.0)
                        alpha *= 255
                    return QColor(int(parts[0]), int(parts[1]), int(parts[2]), int(alpha))
            except (ValueError, IndexError):
                return value_str
        elif value_str.startswith('['):
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                return value_str
        
        # Try converting to a number, otherwise return as a string
        try:
            return int(value_str)
        except ValueError:
            try:
                return float(value_str)
            except ValueError:
                return value_str # It's a non-numeric string like 'solid'