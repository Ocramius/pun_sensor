from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import (
    RestoreEntity,
    ExtraStoredData,
    RestoredExtraData
)
from typing import Any, Dict

from . import PUNDataUpdateCoordinator
from .const import (
    DOMAIN,
    PUN_FASCIA_MONO,
    PUN_FASCIA_F1,
    PUN_FASCIA_F2,
    PUN_FASCIA_F3,
)

from awesomeversion.awesomeversion import AwesomeVersion
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
ATTR_ROUNDED_DECIMALS = "rounded_decimals"

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None) -> None:
    """Inizializza e crea i sensori"""

    # Restituisce il coordinator
    coordinator = hass.data[DOMAIN][config.entry_id]

    # Verifica la versione di Home Assistant
    global has_suggested_display_precision
    has_suggested_display_precision = (AwesomeVersion(HA_VERSION) >= AwesomeVersion("2023.3.0"))

    # Crea i sensori (legati al coordinator)
    entities = []
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_MONO))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F1))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F2))
    entities.append(PUNSensorEntity(coordinator, PUN_FASCIA_F3))
    entities.append(FasciaPUNSensorEntity(coordinator))
    entities.append(PrezzoFasciaPUNSensorEntity(coordinator))

    # Aggiunge i sensori ma non aggiorna automaticamente via web
    # per lasciare il tempo ad Home Assistant di avviarsi
    async_add_entities(entities, update_before_add=False)
    

def fmt_float(num: float):
    """Formatta adeguatamente il numero decimale"""
    if has_suggested_display_precision:
        return num
    
    # In versioni precedenti di Home Assistant che non supportano
    # l'attributo 'suggested_display_precision' restituisce il numero
    # decimale già adeguatamente formattato come stringa
    return format(round(num, 6), '.6f')

class PUNSensorEntity(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Sensore PUN relativo al prezzo medio mensile per fasce"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator, tipo: int) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator e tipo
        self.coordinator = coordinator
        self.tipo = tipo

        # ID univoco sensore basato su un nome fisso
        if (self.tipo == PUN_FASCIA_F3):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_f3')
        elif (self.tipo == PUN_FASCIA_F2):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_f2')
        elif (self.tipo == PUN_FASCIA_F1):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_f1')
        elif (self.tipo == PUN_FASCIA_MONO):
            self.entity_id = ENTITY_ID_FORMAT.format('pun_mono_orario')
        else:
            self.entity_id = None
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_suggested_display_precision = 6
        self._available = False
        self._native_value = 0

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
        self._available = self.coordinator.orari[self.tipo] > 0
        if (self._available): self._native_value = self.coordinator.pun[self.tipo]
        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Determina i dati da salvare per il ripristino successivo"""
        return RestoredExtraData(dict(
            native_value = self._native_value if self._available else None
        ))
    
    async def async_added_to_hass(self) -> None:
        """Entità aggiunta ad Home Assistant"""
        await super().async_added_to_hass()

        # Recupera lo stato precedente, se esiste        
        if (old_data := await self.async_get_last_extra_data()) is not None:
            if (old_native_value := old_data.as_dict().get('native_value')) is not None:
                self._available = True
                self._native_value = old_native_value

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico"""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile"""
        return self._available

    @property
    def native_value(self) -> float:
        """Valore corrente del sensore"""
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura"""
        return f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def state(self) -> str:
        return fmt_float(self.native_value)

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend"""
        return "mdi:chart-line"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        if (self.tipo == PUN_FASCIA_F3):
            return "PUN fascia F3"
        elif (self.tipo == PUN_FASCIA_F2):
            return "PUN fascia F2"
        elif (self.tipo == PUN_FASCIA_F1):
            return "PUN fascia F1"
        elif (self.tipo == PUN_FASCIA_MONO):
            return "PUN mono-orario"
        else:
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Restituisce gli attributi di stato"""
        if has_suggested_display_precision:
            return None
        
        # Nelle versioni precedenti di Home Assistant
        # restituisce un valore arrotondato come attributo
        state_attr = {
            ATTR_ROUNDED_DECIMALS: str(format(round(self.native_value, 3), '.3f'))
        }
        return state_attr

class FasciaPUNSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensore che rappresenta la fascia PUN corrente"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

        # Inizializza coordinator
        self.coordinator = coordinator

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format('pun_fascia_corrente')
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Determina l'aggiornamento automatico"""
        return False

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile"""
        return self.coordinator.fascia_corrente is not None
    
    @property
    def state(self) -> str:
        """Restituisce la fascia corrente come stato"""
        if (self.coordinator.fascia_corrente == 3):
            return "F3"
        elif (self.coordinator.fascia_corrente == 2):
            return "F2"
        elif (self.coordinator.fascia_corrente == 1):
            return "F1"
        else:
            return None

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend"""
        return "mdi:timeline-clock-outline"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        return "Fascia corrente"

class PrezzoFasciaPUNSensorEntity(FasciaPUNSensorEntity, RestoreEntity):
    """Sensore che rappresenta il prezzo PUN della fascia corrente"""

    def __init__(self, coordinator: PUNDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

        # ID univoco sensore basato su un nome fisso
        self.entity_id = ENTITY_ID_FORMAT.format('pun_prezzo_fascia_corrente')
        self._attr_unique_id = self.entity_id
        self._attr_has_entity_name = True

        # Inizializza le proprietà comuni
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_suggested_display_precision = 6
        self._available = False
        self._native_value = 0

    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento dei dati dal coordinator"""
        if super().available:
            if (self.coordinator.fascia_corrente == 3):
                self._available = self.coordinator.orari[PUN_FASCIA_F3] > 0
                self._native_value = self.coordinator.pun[PUN_FASCIA_F3]
            elif (self.coordinator.fascia_corrente == 2):
                self._available = self.coordinator.orari[PUN_FASCIA_F2] > 0
                self._native_value = self.coordinator.pun[PUN_FASCIA_F2]
            elif (self.coordinator.fascia_corrente == 1):
                self._available = self.coordinator.orari[PUN_FASCIA_F1] > 0
                self._native_value = self.coordinator.pun[PUN_FASCIA_F1]
            else:
                self._available = False
                self._native_value = 0
        else:
            self._available = False
            self._native_value = 0
        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Determina i dati da salvare per il ripristino successivo"""
        return RestoredExtraData(dict(
            native_value = self._native_value if self._available else None
        ))
    
    async def async_added_to_hass(self) -> None:
        """Entità aggiunta ad Home Assistant"""
        await super().async_added_to_hass()

        # Recupera lo stato precedente, se esiste        
        if (old_data := await self.async_get_last_extra_data()) is not None:
            if (old_native_value := old_data.as_dict().get('native_value')) is not None:
                self._available = True
                self._native_value = old_native_value

    @property
    def available(self) -> bool:
        """Determina se il valore è disponibile"""
        return self._available

    @property
    def native_value(self) -> float:
        """Restituisce il prezzo della fascia corrente"""
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Unita' di misura"""
        return f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"

    @property
    def state(self) -> str:
        return fmt_float(self.native_value)

    @property
    def icon(self) -> str:
        """Icona da usare nel frontend"""
        return "mdi:currency-eur"

    @property
    def name(self) -> str:
        """Restituisce il nome del sensore"""
        return "Prezzo fascia corrente"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Restituisce gli attributi di stato"""
        if has_suggested_display_precision:
            return None
        
        # Nelle versioni precedenti di Home Assistant
        # restituisce un valore arrotondato come attributo
        state_attr = {
            ATTR_ROUNDED_DECIMALS: str(format(round(self.native_value, 3), '.3f'))
        }
        return state_attr