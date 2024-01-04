"""The openwbmqtt component for controlling the openWB wallbox via home assistant / MQTT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import json
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntityDescription
from homeassistant.const import (
    PERCENTAGE,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfLength,
    UnitOfPower,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

PLATFORMS = [
    Platform.SELECT,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    # Platform.NUMBER,
    # Platform.SWITCH,
]

# Global values
DOMAIN = "openwb2mqtt"
MQTT_ROOT_TOPIC = "mqttroot"
MQTT_ROOT_TOPIC_DEFAULT = "openWB"
DEVICETYPE = "DEVICETYPE"
DEVICEID = "DEVICEID"
MANUFACTURER = "openWB"
MODEL = "openWB"

# Data schema required by configuration flow
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(MQTT_ROOT_TOPIC, default=MQTT_ROOT_TOPIC_DEFAULT): cv.string,
        vol.Required(DEVICETYPE): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value="controller", label="Controller"),
                    SelectOptionDict(value="counter", label="Counter"),
                    SelectOptionDict(value="chargepoint", label="Chargepoint"),
                    SelectOptionDict(value="pv", label="PV Generator"),
                    SelectOptionDict(value="bat", label="Battery"),
                ],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="config_selector_devicetype",  # translation is maintained in translations/<lang>.json via this translation_key
            )
        ),
        vol.Required(DEVICEID): cv.positive_int,
    }
)


def _splitListToFloat(x: list, desiredValueIndex: int) -> float | None:
    """Extract float value from list at a specified index.

    Use this function if the MQTT topic contains a list of values, and you
    want to extract the i-th value from the list.
    For example MQTT = [1.0, 2.0, 3.0] --> extract 3rd value --> sensor value = 3.0
    """
    x = x.replace("[", "")
    x = x.replace("]", "")
    try:
        y = float(x.split(",")[desiredValueIndex])
    except (IndexError, ValueError):
        y = None
    return y


def _convertDateTime(x: str) -> datetime.datetime | None:
    """Convert string to datetime object.

    Assume that the local time zone is the same as the openWB time zone.
    """
    a = json.loads(x).get("timestamp")
    if a is not None:
        dateTimeObject = datetime.datetime.strptime(a, "%m/%d/%Y, %H:%M:%S")
        dateTimeObject = dateTimeObject.astimezone(tz=None)
        return dateTimeObject
    return a


@dataclass
class openwbSensorEntityDescription(SensorEntityDescription):
    """Enhance the sensor entity description for openWB."""

    value_fn: Callable | None = None
    valueMap: dict | None = None
    mqttTopicCurrentValue: str | None = None


@dataclass
class openwbBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Enhance the sensor entity description for openWB."""

    state: Callable | None = None
    mqttTopicCurrentValue: str | None = None


@dataclass
class openwbSelectEntityDescription(SelectEntityDescription):
    """Enhance the select entity description for openWB."""

    valueMapCommand: dict | None = None
    valueMapCurrentValue: dict | None = None
    mqttTopicCommand: str | None = None
    mqttTopicCurrentValue: str | None = None
    value_fn: Callable | None = None
    modes: list | None = None


@dataclass
class openwbSwitchEntityDescription(SwitchEntityDescription):
    """Enhance the select entity description for openWB."""

    mqttTopicCommand: str | None = None
    mqttTopicCurrentValue: str | None = None
    mqttTopicChargeMode: str | None = None


@dataclass
class openWBNumberEntityDescription(NumberEntityDescription):
    """Enhance the number entity description for openWB."""

    mqttTopicCommand: str | None = None
    mqttTopicCurrentValue: str | None = None
    mqttTopicChargeMode: str | None = None


SENSORS_PER_CHARGEPOINT = [
    openwbSensorEntityDescription(
        key="get/currents",
        name="Strom (L1)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="get/currents",
        name="Strom (L2)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="get/currents",
        name="Strom (L3)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="get/daily_imported",
        name="Geladene Energie (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="get/daily_exported",
        name="Entladene Energie (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        icon="mdi:counter",
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="get/evse_current",
        name="Ladestromvorgabe",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda x: round(float(x) / 1000.0, 1),
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        icon="mdi:current-ac",
    ),
    openwbSensorEntityDescription(
        key="get/exported",
        name="Entladene Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:counter",
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="get/fault_str",
        name="Fehlerbeschreibung",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.strip('"').strip(".")[0:255],
    ),
    openwbSensorEntityDescription(
        key="get/imported",
        name="Geladene Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="get/phases_in_use",
        name="Aktive Phasen",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    openwbSensorEntityDescription(
        key="get/power",
        name="Ladeleistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-electric-outline",
    ),
    openwbSensorEntityDescription(
        key="get/state_str",
        name="Ladezustand",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.strip('"').strip(".")[0:255],
    ),
    openwbSensorEntityDescription(
        key="get/voltages",
        name="Spannung (L1)",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="get/voltages",
        name="Spannung (L2)",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="get/voltages",
        name="Spannung (L3)",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="get/power_factors",
        name="Leistungsfaktor (L1)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 0),
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="get/power_factors",
        name="Leistungsfaktor (L2)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 1),
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="get/power_factors",
        name="Leistungsfaktor (L3)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 2),
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="get/powers",
        name="Leistung (L1)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:car-electric-outline",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="get/powers",
        name="Leistung (L2)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:car-electric-outline",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="get/powers",
        name="Leistung (L3)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:car-electric-outline",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="get/frequency",
        name="Frequenz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        # icon="mdi:current-ac",
    ),
    openwbSensorEntityDescription(
        key="config",
        name="Ladepunkt",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        value_fn=lambda x: json.loads(x).get("name").replace('"', ""),
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/info",
        name="Fahrzeug-ID",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        value_fn=lambda x: json.loads(x).get("id"),
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/info",
        name="Fahrzeug",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        value_fn=lambda x: json.loads(x).get("name").replace('"', ""),
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/config",
        name="Lade-Profil",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_visible_default=False,
        value_fn=lambda x: json.loads(x).get("charge_template"),
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/config",
        name="Lademodus",
        device_class=None,
        native_unit_of_measurement=None,
        value_fn=lambda x: json.loads(x).get("chargemode"),
        valueMap={
            "standby": "Standby",
            "stop": "Stop",
            "scheduled_charging": "Scheduled Charging",
            "time_charging": "Time Charging",
            "instant_charging": "Instant Charging",
            "pv_charging": "PV Charging",
        },
        translation_key="sensor_lademodus",
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/soc",
        name="Ladung",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        suggested_display_precision=0,
        value_fn=lambda x: json.loads(x).get("soc"),
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/soc",
        name="SoC-Datenaktualisierung",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:clock-time-eight",
        value_fn=lambda x: _convertDateTime(x),
        # Example: "01/02/2024, 15:29:12"
    ),
    openwbSensorEntityDescription(
        key="get/rfid",
        name="Zuletzt gescannter RFID-Tag",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:tag-multiple",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="get/connected_vehicle/soc",
        name="Geladene Entfernung",
        device_class=None,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        entity_registry_enabled_default=False,
        value_fn=lambda x: json.loads(x).get("range_charged"),
        suggested_display_precision=1,
    ),
]

BINARY_SENSORS_PER_CHARGEPOINT = [
    openwbBinarySensorEntityDescription(
        key="plug_state",
        name="Ladekabel",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    openwbBinarySensorEntityDescription(
        key="charge_state",
        name="Autoladestatus",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    openwbBinarySensorEntityDescription(
        key="fault_state",
        name="Fehler",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

SELECTS_PER_CHARGEPOINT = [
    openwbSelectEntityDescription(
        key="chargemode",
        entity_category=EntityCategory.CONFIG,
        name="Lademodus",
        translation_key="selector_chargepoint_chargemode",  # translation is maintained in translations/<lang>.json via this translation_key
        valueMapCurrentValue={
            "instant_charging": "Instant Charging",
            "scheduled_charging": "Scheduled Charging",
            "pv_charging": "PV Charging",
            "standby": "Standby",
            "stop": "Stop",
            # "time_charging": "Time Charging",
        },
        valueMapCommand={
            "Instant Charging": "instant_charging",
            "Scheduled Charging": "scheduled_charging",
            "PV Charging": "pv_charging",
            "Standby": "standby",
            "Stop": "stop",
            # "Time Charging": "time_charging",
        },
        mqttTopicCommand="set/vehicle/template/charge_template/_chargeTemplateID_/chargemode/selected",
        mqttTopicCurrentValue="get/connected_vehicle/config",
        options=[
            "Instant Charging",
            "Scheduled Charging",
            "PV Charging",
            "Stop",
            "Standby",
        ],
        value_fn=lambda x: json.loads(x).get("chargemode"),
    ),
]

SENSORS_PER_COUNTER = [
    openwbSensorEntityDescription(
        key="voltages",
        name="Spannung (L1)",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="voltages",
        name="Spannung (L2)",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="voltages",
        name="Spannung (L3)",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="power_factors",
        name="Leistungsfaktor (L1)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 0),
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="power_factors",
        name="Leistungsfaktor (L2)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 1),
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="power_factors",
        name="Leistungsfaktor (L3)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 2),
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="powers",
        name="Leistung (L1)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:transmission-tower",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="powers",
        name="Leistung (L2)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:transmission-tower",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="powers",
        name="Leistung (L3)",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:transmission-tower",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="frequency",
        name="Frequenz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        # icon="mdi:current-ac",
    ),
    openwbSensorEntityDescription(
        key="currents",
        name="Strom (L1)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="currents",
        name="Strom (L2)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="currents",
        name="Strom (L3)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="power",
        name="Leistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        # state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        icon="mdi:transmission-tower",
    ),
    openwbSensorEntityDescription(
        key="fault_str",
        name="Fehlerbeschreibung",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.strip('"').strip(".")[0:255],
    ),
    openwbSensorEntityDescription(
        key="exported",
        name="Exportierte Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:transmission-tower-export",
    ),
    openwbSensorEntityDescription(
        key="imported",
        name="Importierte Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:transmission-tower-import",
    ),
    openwbSensorEntityDescription(
        key="daily_imported",
        name="Importierte Energie (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=1,
        icon="mdi:transmission-tower-import",
    ),
    openwbSensorEntityDescription(
        key="daily_exported",
        name="Exportierte Energie (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=1,
        icon="mdi:transmission-tower-export",
    ),
]

BINARY_SENSORS_PER_COUNTER = [
    openwbBinarySensorEntityDescription(
        key="fault_state",
        name="Fehler",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

SENSORS_PER_BATTERY = [
    openwbSensorEntityDescription(
        key="soc",
        name="Ladung",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        # icon="mdi:transmission-tower",
    ),
    openwbSensorEntityDescription(
        key="power",
        name="Leistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        icon="mdi:battery-charging",
    ),
    openwbSensorEntityDescription(
        key="fault_str",
        name="Fehlerbeschreibung",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.strip('"').strip(".")[0:255],
    ),
    openwbSensorEntityDescription(
        key="exported",
        name="Entladene Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:battery-arrow-up",
    ),
    openwbSensorEntityDescription(
        key="imported",
        name="Geladene Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:battery-arrow-down",
    ),
    openwbSensorEntityDescription(
        key="daily_imported",
        name="Geladene Energie (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=1,
        icon="mdi:battery-arrow-down",
    ),
    openwbSensorEntityDescription(
        key="daily_exported",
        name="Entladene Energie (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=1,
        icon="mdi:battery-arrow-up",
    ),
]

BINARY_SENSORS_PER_BATTERY = [
    openwbBinarySensorEntityDescription(
        key="fault_state",
        name="Fehler",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

SENSORS_PER_PVGENERATOR = [
    openwbSensorEntityDescription(
        key="daily_exported",
        name="Zählerstand (Heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=1,
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="monthly_exported",
        name="Zählerstand (Monat)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=0,
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="yearly_exported",
        name="Zählerstand (Jahr)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=0,
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="exported",
        name="Zählerstand (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000.0, 3),
        suggested_display_precision=0,
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="power",
        name="Leistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
        icon="mdi:solar-power",
        suggested_display_precision=0,
        value_fn=lambda x: abs(float(x)),
    ),
    openwbSensorEntityDescription(
        key="currents",
        name="Strom (L1)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 0),
    ),
    openwbSensorEntityDescription(
        key="currents",
        name="Strom (L2)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="currents",
        name="Strom (L3)",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        value_fn=lambda x: _splitListToFloat(x, 2),
    ),
    openwbSensorEntityDescription(
        key="fault_str",
        name="Fehlerbeschreibung",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.strip('"').strip(".")[0:255],
    ),
]

BINARY_SENSORS_PER_PVGENERATOR = [
    openwbBinarySensorEntityDescription(
        key="fault_state",
        name="Fehler",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

SENSORS_CONTROLLER = [
    # System
    openwbSensorEntityDescription(
        key="system/ip_address",
        name="IP-Adresse",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:earth",
        value_fn=lambda x: x.replace('"', ""),
    ),
    openwbSensorEntityDescription(
        key="system/version",
        name="Version",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:folder-clock",
        value_fn=lambda x: x.replace('"', ""),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="Datenaktualisierung",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:clock-time-eight",
        value_fn=lambda x: datetime.datetime.fromtimestamp(
            int(json.loads(x).get("timestamp")), tz=ZoneInfo("UTC")
        ),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="Netzbezug/-einspeisung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:transmission-tower",
        value_fn=lambda x: round(1000 * float(json.loads(x).get("grid")), 0),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="Hausverbrauch",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:home-lightning-bolt",
        value_fn=lambda x: round(1000 * float(json.loads(x).get("house-power")), 0),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="PV-Leistung (Gesamt)",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:solar-power",
        value_fn=lambda x: round(1000 * float(json.loads(x).get("pv-all")), 0),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="Ladeleistung (Gesamt)",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:car-electric-outline",
        value_fn=lambda x: round(1000 * float(json.loads(x).get("charging-all")), 0),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="Batterieleistung (Gesamt)",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:battery-charging",
        value_fn=lambda x: round(1000 * float(json.loads(x).get("bat-all-power")), 0),
    ),
    openwbSensorEntityDescription(
        key="system/lastlivevaluesJson",
        name="Batterieladung (Gesamt)",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda x: json.loads(x).get("bat-all-soc"),
    ),
]
