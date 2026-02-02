# services/treatment_planner.py

import logging
import sys
import os
from typing import Dict, Any, Optional

# This allows importing the config file from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

logger = logging.getLogger(__name__)

class TreatmentPlanner:
    """
    Implements the logic for creating specific treatment actions based on a
    pre-determined treatment group and environmental sensor data.
    """

    def __init__(self):
        logger.info("TreatmentPlanner initialized.")
        # Store groups for quick lookup
        self._groups = {group['name']: group for group in config.TREATMENT_GROUPS}
        self._stress_to_group_map = {
            stress: group for group in config.TREATMENT_GROUPS for stress in group["targets"]
        }

    def get_group_for_stress(self, stress_name: str) -> Optional[Dict[str, Any]]:
        """
        A helper method to find the corresponding treatment group for a given stress.
        
        Args:
            stress_name (str): The name of the detected stress class.

        Returns:
            Optional[Dict[str, Any]]: The configuration dictionary for the matching
                                      treatment group, or None if no match is found.
        """
        return self._stress_to_group_map.get(stress_name)

    def create_plan_for_group(self, group: Dict[str, Any], sensor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Creates a single treatment action based on a pre-selected treatment group
        and adjusts it based on sensor data. Returns None if no treatment is needed.

        Args:
            group (Dict[str, Any]): The configuration dictionary for the treatment group
                                    (e.g., config.FERTILIZER_GROUP).
            sensor_data (Dict[str, Any]): The latest sensor readings (T, H).

        Returns:
            Optional[Dict[str, Any]]: A dictionary describing the treatment action,
                                      or None if no action should be taken.
        """
        if not group:
            logger.warning("create_plan_for_group called with an invalid group.")
            return None

        logger.info(f"Creating treatment plan for group '{group['name']}'.")
        
        base_volume = 20.0  # Base spray volume in mL
        temp = sensor_data.get('T', 25.0)
        humidity = sensor_data.get('H', 60.0)
        
        adjusted_volume = float(base_volume)
        
        # Environmental rule: High humidity can promote fungal growth, so don't spray water-based solutions.
        if humidity > config.HIGH_HUMIDITY_THRESHOLD:
            logger.warning(f"High humidity ({humidity}%) detected. Skipping spray to prevent fungal issues.")
            return None
        
        # Environmental rule: High temperatures can cause leaf burn when spraying. Reduce volume.
        if temp > config.HIGH_TEMP_THRESHOLD:
            adjusted_volume *= 0.75
            logger.info(f"High temperature ({temp}°C) detected. Reducing spray volume to {adjusted_volume:.1f}mL.")
        
        if adjusted_volume > 1.0:
            return {
                "action": "spray",
                "tank_num": group['tank'],
                "volume_ml": adjusted_volume,
                "treatment_name": group['name']
            }
        else:
            logger.warning("Adjusted spray volume is too low (<1.0mL). No action will be taken.")
            return None
        
