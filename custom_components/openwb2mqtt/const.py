"""The openwbmqtt component for controlling the openWB wallbox via home assistant / MQTT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import json

import pytz
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
    selector,
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
    ),
    # openwbSensorEntityDescription(
    #     key="get/evse_current",
    #     name="EVSE Strom",
    #     device_class=SensorDeviceClass.CURRENT,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    #     icon="mdi:current-ac",
    # ),
    openwbSensorEntityDescription(
        key="get/exported",
        name="Entladene Energie (Gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda x: round(float(x) / 1000, 3),
        suggested_display_precision=0,
        icon="mdi:counter",
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
    ),
    openwbSensorEntityDescription(
        key="get/power_factors",
        name="Leistungsfaktor (L2)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="get/power_factors",
        name="Leistungsfaktor (L3)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 2),
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
    ),
    openwbSensorEntityDescription(
        key="power_factors",
        name="Leistungsfaktor (L2)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 1),
    ),
    openwbSensorEntityDescription(
        key="power_factors",
        name="Leistungsfaktor (L3)",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        # icon=,
        value_fn=lambda x: _splitListToFloat(x, 2),
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
            int(json.loads(x).get("timestamp")), tz=pytz.timezone("UTC")
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


# List of global sensors that are relevant to the entire wallbox
SENSORS_GLOBAL = [
    openwbSensorEntityDescription(
        key="system/Uptime",
        name="Uptime",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:web-clock",
    ),
    openwbSensorEntityDescription(
        key="system/lastRfId",
        name="zuletzt gescannter RFID-Tag",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:tag-multiple-outline",
    ),
    # Global
    openwbSensorEntityDescription(
        key="global/cpuModel",
        name="CPU Modell",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cpu-32-bit",
    ),
    openwbSensorEntityDescription(
        key="global/cpuUse",
        name="CPU Nutzung",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cpu-32-bit",
    ),
    openwbSensorEntityDescription(
        key="global/cpuTemp",
        name="CPU Temperatur",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:thermometer-alert",
    ),
    openwbSensorEntityDescription(
        key="global/memTotal",
        name="RAM Verfügbar",
        device_class=None,
        native_unit_of_measurement="MB",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:memory",
    ),
    openwbSensorEntityDescription(
        key="global/memUse",
        name="RAM Genutzt",
        device_class=None,
        native_unit_of_measurement="MB",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:memory",
    ),
    openwbSensorEntityDescription(
        key="global/memFree",
        name="RAM Frei",
        device_class=None,
        native_unit_of_measurement="MB",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:memory",
    ),
    openwbSensorEntityDescription(
        key="global/diskUse",
        name="Disk Verfügbar",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:harddisk",
    ),
    openwbSensorEntityDescription(
        key="global/diskFree",
        name="Disk Frei",
        device_class=None,
        native_unit_of_measurement=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:harddisk",
    ),
    openwbSensorEntityDescription(
        key="global/WHouseConsumption",
        name="Hausverbrauch",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        icon="mdi:home-lightning-bolt-outline",
    ),
    openwbSensorEntityDescription(
        key="global/DailyYieldHausverbrauchKwh",
        name="Heutiger Hausverbrauch (kWh)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="global/WAllChargePoints",
        name="Ladeleistung aller Ladepunkte",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-charging-50",
    ),
    openwbSensorEntityDescription(
        key="global/DailyYieldAllChargePointsKwh",
        name="Tagesverbrauch aller Ladepunkte",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:counter",
    ),
    # PV
    openwbSensorEntityDescription(
        key="pv/W",
        name="PV-Leistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x) * (-1.0)),
        icon="mdi:solar-power-variant-outline",
    ),
    openwbSensorEntityDescription(
        key="pv/WhCounter",
        name="PV-Gesamtertrag",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x) / 1000.0, 2),
        icon="mdi:counter",
    ),
    openwbSensorEntityDescription(
        key="pv/DailyYieldKwh",
        name="Heutiger PV-Ertrag (kWh)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:counter",
    ),
    # EVU
    openwbSensorEntityDescription(
        key="evu/W",
        name="EVU-Leistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        icon="mdi:transmission-tower",
    ),
    openwbSensorEntityDescription(
        key="evu/WhImported",
        name="Netzbezug",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x) / 1000.0, 2),
        icon="mdi:transmission-tower-export",
    ),
    openwbSensorEntityDescription(
        key="evu/WhExported",
        name="Netzeinspeisung",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x) / 1000.0, 2),
        icon="mdi:transmission-tower-import",
    ),
    openwbSensorEntityDescription(
        key="evu/DailyYieldExportKwh",
        name="Heutiger Strom-Export (kWh)",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:transmission-tower-import",
    ),
    openwbSensorEntityDescription(
        key="evu/DailyYieldImportKwh",
        name="Heutiger Strom-Bezug (kWh)",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:transmission-tower-export",
    ),
    openwbSensorEntityDescription(
        key="pv/WhCounter",
        name="PV-Gesamtertrag",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:counter",
    ),
    # Housebattery
    openwbSensorEntityDescription(
        key="housebattery/WhImported",
        name="Batteriebezug",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x) / 1000.0, 2),
        icon="mdi:battery-arrow-down-outline",
    ),
    openwbSensorEntityDescription(
        key="housebattery/WhExported",
        name="Batterieeinspeisung",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x) / 1000.0, 2),
        icon="mdi:battery-arrow-up-outline",
    ),
    openwbSensorEntityDescription(
        key="housebattery/DailyYieldExportKwh",
        name="Batterieentladung Heute (kWh)",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:battery-arrow-up-outline",
    ),
    openwbSensorEntityDescription(
        key="housebattery/DailyYieldImportKwh",
        name="Batterieladung Heute (kWh)",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x), 2),
        icon="mdi:battery-arrow-down-outline",
    ),
    openwbSensorEntityDescription(
        key="housebattery/W",
        name="Batterieleistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda x: round(float(x)),
        icon="mdi:home-battery-outline",
    ),
    openwbSensorEntityDescription(
        key="housebattery/%Soc",
        name="SoC (Batterie)",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        icon="mdi:battery-charging-low",
    ),
]

SENSORS_PER_LP = [
    openwbSensorEntityDescription(
        key="W",
        name="Ladeleistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    openwbSensorEntityDescription(
        key="energyConsumptionPer100km",
        name="Durchschnittsverbrauch (pro 100 km)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="socFaultState",
        name="Soc-Fehlerstatus",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:alert-circle-outline",
    ),
    openwbSensorEntityDescription(
        key="socFaultStr",
        name="Soc-Fehlertext",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:alert-circle-outline",
    ),
    openwbSensorEntityDescription(
        key="lastRfId",
        name="zuletzt gescannter RFID-Tag",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:tag-multiple",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="AConfigured",
        name="Ladestromvorgabe",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    openwbSensorEntityDescription(
        key="kmCharged",
        name="Geladene Entfernung",
        device_class=None,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
    ),
    openwbSensorEntityDescription(
        key="%Soc",
        name="SoC",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    openwbSensorEntityDescription(
        key="kWhActualCharged",
        name="Geladene Energie (akt. Ladevorgang)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:counter",
        value_fn=lambda x: round(float(x), 2),
    ),
    openwbSensorEntityDescription(
        key="kWhChargedSincePlugged",
        name="Geladene Energie (seit Anstecken)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:counter",
        value_fn=lambda x: round(float(x), 2),
    ),
    openwbSensorEntityDescription(
        key="kWhDailyCharged",
        name="Geladene Energie (heute)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:counter",
        value_fn=lambda x: round(float(x), 2),
    ),
    openwbSensorEntityDescription(
        key="kWhCounter",
        name="Geladene Energie (gesamt)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        value_fn=lambda x: round(float(x), 2),
    ),
    openwbSensorEntityDescription(
        key="countPhasesInUse",
        name="Aktive Phasen",
        device_class=None,
        native_unit_of_measurement=None,
    ),
    openwbSensorEntityDescription(
        key="TimeRemaining",
        name="Voraus. Ladeende",
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        icon="mdi:alarm",
    ),
    openwbSensorEntityDescription(
        key="strChargePointName",
        name="Ladepunktsbezeichnung",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:form-textbox",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="PfPhase1",
        name="Leistungsfaktor (Phase 1)",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="PfPhase2",
        name="Leistungsfaktor (Phase 2)",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="PfPhase3",
        name="Leistungsfaktor (Phase 3)",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="VPhase1",
        name="Spannung (Phase 1)",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="VPhase2",
        name="Spannung (Phase 2)",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="VPhase3",
        name="Spannung (Phase 3)",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
    ),
    openwbSensorEntityDescription(
        key="APhase1",
        name="Stromstärke (Phase 1)",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    openwbSensorEntityDescription(
        key="APhase2",
        name="Stromstärke (Phase 2)",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    openwbSensorEntityDescription(
        key="APhase3",
        name="Stromstärke (Phase 3)",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
]

# add binarysensor system/updateinprogress
BINARY_SENSORS_GLOBAL = [
    openwbBinarySensorEntityDescription(
        key="system/updateInProgress",
        name="Update wird durchgeführt",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=None,
        icon="mdi:update",
    ),
]

BINARY_SENSORS_PER_LP = [
    openwbBinarySensorEntityDescription(
        key="ChargeStatus",
        name="Ladepunkt freigegeben",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    openwbBinarySensorEntityDescription(
        key="ChargePointEnabled",
        name="Ladepunkt aktiv",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    openwbBinarySensorEntityDescription(
        key="boolDirectModeChargekWh",
        name="Begrenzung Energie (Modus Sofortladen)",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-charging",
    ),
    openwbBinarySensorEntityDescription(
        key="boolDirectChargeModeSoc",
        name="Begrenzung SoC (Modus Sofortladen)",
        device_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-unknown",
    ),
    openwbBinarySensorEntityDescription(
        key="boolChargeAtNight",
        name="Nachtladen aktiv",
        device_class=None,
        icon="mdi:weather-night",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    openwbBinarySensorEntityDescription(
        key="boolPlugStat",
        name="Ladekabel",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    openwbBinarySensorEntityDescription(
        key="boolChargeStat",
        name="Autoladestatus",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
]

SELECTS_GLOBAL = [
    openwbSelectEntityDescription(
        key="global/ChargeMode",
        entity_category=EntityCategory.CONFIG,
        name="Lademodus",
        valueMapCurrentValue={
            0: "Sofortladen",
            1: "Min+PV-Laden",
            2: "PV-Laden",
            3: "Stop",
            4: "Standby",
        },
        valueMapCommand={
            "Sofortladen": 0,
            "Min+PV-Laden": 1,
            "PV-Laden": 2,
            "Stop": 3,
            "Standby": 4,
        },
        mqttTopicCommand="set/ChargeMode",
        mqttTopicCurrentValue="global/ChargeMode",
        modes=[
            "Sofortladen",
            "Min+PV-Laden",
            "PV-Laden",
            "Stop",
            "Standby",
        ],
    ),
    openwbSelectEntityDescription(
        key="config/get/pv/priorityModeEVBattery",
        entity_category=EntityCategory.CONFIG,
        name="Vorrang im Lademodus PV-Laden",
        valueMapCurrentValue={
            0: "Speicher",
            1: "Fahrzeug",
        },
        valueMapCommand={
            "Speicher": 0,
            "Fahrzeug": 1,
        },
        mqttTopicCommand="config/set/pv/priorityModeEVBattery",
        mqttTopicCurrentValue="config/get/pv/priorityModeEVBattery",
        modes=[
            "Speicher",
            "Fahrzeug",
        ],
    ),
    openwbSelectEntityDescription(
        key="config/get/u1p3p/nurpvPhases",
        entity_category=EntityCategory.CONFIG,
        name="Phasenumschaltung PV-Laden",
        valueMapCurrentValue={
            1: "1 Phase",
            3: "3 Phasen",
            4: "Auto",
        },
        valueMapCommand={
            "1 Phase": 1,
            "3 Phasen": 3,
            "Auto": 4,
        },
        mqttTopicCommand="config/set/u1p3p/nurpvPhases",
        mqttTopicCurrentValue="config/get/u1p3p/nurpvPhases",
        modes=[
            "1 Phase",
            "3 Phasen",
            "Auto",
        ],
    ),
    openwbSelectEntityDescription(
        key="config/get/u1p3p/minundpvPhases",
        entity_category=EntityCategory.CONFIG,
        name="Phasenumschaltung Min+PV-Laden",
        valueMapCurrentValue={
            1: "1 Phase",
            3: "3 Phasen",
            4: "Auto",
        },
        valueMapCommand={
            "1 Phase": 1,
            "3 Phasen": 3,
            "Auto": 4,
        },
        mqttTopicCommand="config/set/u1p3p/minundpvPhases",
        mqttTopicCurrentValue="config/get/u1p3p/minundpvPhases",
        modes=[
            "1 Phase",
            "3 Phasen",
            "Auto",
        ],
    ),
    openwbSelectEntityDescription(
        key="config/get/u1p3p/sofortPhases",
        entity_category=EntityCategory.CONFIG,
        name="Phasenumschaltung Sofort-Laden",
        valueMapCurrentValue={
            1: "1 Phase",
            3: "3 Phasen",
            4: "Auto",
        },
        valueMapCommand={
            "1 Phase": 1,
            "3 Phasen": 3,
            "Auto": 4,
        },
        mqttTopicCommand="config/set/u1p3p/sofortPhases",
        mqttTopicCurrentValue="config/get/u1p3p/sofortPhases",
        modes=[
            "1 Phase",
            "3 Phasen",
            "Auto",
        ],
    ),
    openwbSelectEntityDescription(
        key="config/get/u1p3p/nachtPhases",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        name="Phasenumschaltung (Modus Nacht-Laden)",
        valueMapCurrentValue={
            1: "1 Phase",
            3: "3 Phasen",
            4: "Auto",
        },
        valueMapCommand={
            "1 Phase": 1,
            "3 Phasen": 3,
            "Auto": 4,
        },
        mqttTopicCommand="config/set/u1p3p/nachtPhases",
        mqttTopicCurrentValue="config/get/u1p3p/nachtPhases",
        modes=[
            "1 Phase",
            "3 Phasen",
            "Auto",
        ],
    ),
    openwbSelectEntityDescription(
        key="config/get/u1p3p/standbyPhases",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        name="Phasenumschaltung (Modus Standby)",
        valueMapCurrentValue={
            1: "1 Phase",
            3: "3 Phasen",
            4: "Auto",
        },
        valueMapCommand={
            "1 Phase": 1,
            "3 Phasen": 3,
            "Auto": 4,
        },
        mqttTopicCommand="config/set/u1p3p/standbyPhases",
        mqttTopicCurrentValue="config/get/u1p3p/standbyPhases",
        modes=[
            "1 Phase",
            "3 Phasen",
            "Auto",
        ],
    ),
]

SELECTS_PER_LP = [
    openwbSelectEntityDescription(
        key="chargeLimitation",
        entity_category=EntityCategory.CONFIG,
        name="Ladebegrenzung (Modus Sofortladen)",
        valueMapCurrentValue={
            0: "Keine",
            1: "Energie",
            2: "SoC",
        },
        valueMapCommand={
            "Keine": 0,
            "Energie": 1,
            "SoC": 2,
        },
        mqttTopicCommand="chargeLimitation",
        mqttTopicCurrentValue="chargeLimitation",
        modes=[
            "Keine",
            "Energie",
            "SoC",
        ],
    ),
]

SWITCHES_PER_LP = [
    openwbSwitchEntityDescription(
        key="ChargePointEnabled",
        entity_category=EntityCategory.CONFIG,
        name="Ladepunkt aktiv",
        mqttTopicCommand="ChargePointEnabled",
        mqttTopicCurrentValue="ChargePointEnabled",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    openwbSwitchEntityDescription(
        key="PriceBasedCharging",
        entity_category=EntityCategory.CONFIG,
        name="Preisbasiertes Laden (Modus Sofortladen)",
        device_class=SwitchDeviceClass.SWITCH,
        mqttTopicCommand="etBasedCharging",
        mqttTopicCurrentValue="etBasedCharging",
        mqttTopicChargeMode="sofort",
    ),
]

NUMBERS_GLOBAL = [
    openWBNumberEntityDescription(
        key="minCurrentMinPv",
        name="Mindestladestrom (Modus Min+PV-Laden)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class="Power",
        native_min_value=6.0,
        native_max_value=16.0,
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        # icon=
        mqttTopicCommand="minCurrentMinPv",
        mqttTopicCurrentValue="minCurrentMinPv",
        mqttTopicChargeMode="pv",
        icon="mdi:current-ac",
    ),
]

NUMBERS_PER_LP = [
    openWBNumberEntityDescription(
        key="current",
        name="Ladestromvorgabe (Modus Sofortladen)",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class="Power",
        native_min_value=6.0,
        native_max_value=16.0,
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        # icon=
        mqttTopicCommand="current",
        mqttTopicCurrentValue="current",
        mqttTopicChargeMode="sofort",
        icon="mdi:current-ac",
    ),
    openWBNumberEntityDescription(
        key="energyToCharge",
        name="Energiebegrenzung (Modus Sofortladen)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class="Energy",
        native_min_value=2.0,
        native_max_value=100.0,
        native_step=2.0,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:battery-charging",
        mqttTopicCommand="energyToCharge",
        mqttTopicCurrentValue="energyToCharge",
        mqttTopicChargeMode="sofort",
    ),
    openWBNumberEntityDescription(
        key="socToChargeTo",
        name="SoC-Begrenzung (Modus Sofortladen)",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery-unknown",
        native_min_value=5.0,
        native_max_value=100.0,
        native_step=5.0,
        entity_category=EntityCategory.CONFIG,
        # icon=
        mqttTopicCommand="socToChargeTo",
        mqttTopicCurrentValue="socToChargeTo",
        mqttTopicChargeMode="sofort",
    ),
    openWBNumberEntityDescription(
        key="manualSoc",
        name="Aktueller SoC (Manuelles SoC Modul)",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery-unknown",
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
        entity_category=EntityCategory.CONFIG,
        mqttTopicCommand="manualSoc",
        mqttTopicCurrentValue="manualSoc",
        mqttTopicChargeMode=None,
        entity_registry_enabled_default=False,
    ),
]
