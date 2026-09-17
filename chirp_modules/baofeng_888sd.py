
# Experimental CHIRP driver for the Baofeng/888SD-class GMSK
# 16-channel radio.
#
# v0.18 models the programming password as an independent 0-16 byte
# ASCII value, keeps dealer entries only as convenience presets, and
# restricts subsystemID to the verified uint8 range 0-255. Empty normal
# passwords are supported and encoded as the complete 16-byte all-zero
# password field. The effective new-password field follows the selected
# source: editable only for Custom, otherwise read-only and auto-filled.
# Upload is permitted only after a live download in the same CHIRP session,
# and only verified channel or basic-setting bytes may differ from the
# downloaded baseline:
#   * serial initialization
#   * CN59500 normal programming authentication
#   * 888SD clone-mode identification
#   * sparse raw-image download
#   * basic 16-channel decoding

import base64
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
import re
import struct
import time

from chirp import chirp_common
from chirp import directory
from chirp import errors
from chirp import memmap
from chirp import util
from chirp.settings import (
    RadioSetting,
    RadioSettingGroup,
    RadioSettings,
    RadioSettingValueBoolean,
    RadioSettingValueInteger,
    RadioSettingValueList,
    RadioSettingValueMap,
    RadioSettingValueString,
)

LOG = logging.getLogger(__name__)

ACK = b"\x06"
REJECT = b"\x04"

PROGRAM_PROBE = bytes.fromhex("02 70 72 4F 47 52 41 4D")
NORMAL_PASSWORD_ENTRY = bytes.fromhex("02 75 63 62 66 70 77 64")
AUTH_HANDSHAKE = bytes.fromhex("10 C5 EA 35")

# Hidden provisioning protocol verified on real 888SD hardware.
SUPERADMIN_ENTRY = bytes.fromhex("02 75 63 66 62 77 70 64")
PASSWORD_CHANGE_COMMAND = bytes.fromhex("20 EA AB 5C")
CONFIG_ENTRY = bytes.fromhex("02 60 62 4F 41 57 52 4D")
CONFIG_CONFIRM = b"\x20"
SUPERADMIN_PASSWORD = b"admin#jzssjb1".ljust(16, b"\x00")

# protocolCode A -> jH("A") == 0x8082
CLONE_MAGIC = bytes.fromhex("02 80 82 4F 47 52 41 4D")
CLONE_IDENT = bytes.fromhex("50 33 31 30 37 F7 00 00")
CLONE_PROBE = bytes.fromhex("52 01 30 08")
CLONE_PROBE_REPLY = bytes.fromhex(
    "57 01 30 08 FF FF FF FF FF FF FF FF"
)

CMD_EXIT = b"\x45"
WRITE_TRANSITION_REPLY = b"\x46"

IMAGE_SIZE = 0x03E0
BLOCK_SIZE = 0x08
CHANNEL_BASE = 0x0010
CHANNEL_SIZE = 0x10
CHANNEL_COUNT = 16

POWER_LEVELS = [
    chirp_common.PowerLevel("Low"),
    chirp_common.PowerLevel("High"),
]

# First development target: the radio successfully migrated to the
# Baofeng dealer profile on 2026-07-15.
DEFAULT_DEALER_CODE = "CN59500"

# The radio protocol does not bind its normal programming password to a
# dealer profile. It accepts one independently chosen ASCII password field,
# padded to 16 bytes on the wire.
#
# The original CPS dealer table is retained only as a convenience: for those
# presets, the CPS generates the password text by Base64-encoding the dealer
# code and truncating/padding it to the 16-byte field.
KNOWN_PASSWORD_PRESETS = [
    ("POFUNG / 外贸体验版 (CPS default subsystemID 0)", "POFUNG", 0),
    ("CN59500 / 宝锋 (CPS default subsystemID 1)", "CN59500", 1),
    ("CN59501 / 王青红 (CPS default subsystemID 2)", "CN59501", 2),
    ("CN59502 / 王鑫源 (CPS default subsystemID 3)", "CN59502", 3),
    ("CN59503 / 李木旺 (CPS default subsystemID 4)", "CN59503", 4),
    ("CN59504 / 王景松 (CPS default subsystemID 5)", "CN59504", 5),
    ("CN02801 / 邓小松 (CPS default subsystemID 6)", "CN02801", 6),
    ("CN02501 / 姜克明 (CPS default subsystemID 7)", "CN02501", 7),
    ("CN53601 / 张丽丽 (CPS default subsystemID 8)", "CN53601", 8),
    ("CN93101 / 陈军 (CPS default subsystemID 9)", "CN93101", 9),
    ("CN53201 / 吴端乐 / Suofei (CPS default subsystemID 10)",
     "CN53201", 10),
    ("CN53901 / LZF (CPS default subsystemID 11)", "CN53901", 11),
]
KNOWN_PRESET_BY_CODE = {
    code: (label, sid) for label, code, sid in KNOWN_PASSWORD_PRESETS
}

PASSWORD_SOURCE_KEEP = "keep"
PASSWORD_SOURCE_EMPTY = "empty"
PASSWORD_SOURCE_CUSTOM = "custom"
PASSWORD_SOURCE_OPTIONS = [
    ("Keep current password (保持当前密码)", PASSWORD_SOURCE_KEEP),
    ("Empty password / 16×00 (空密码)", PASSWORD_SOURCE_EMPTY),
    ("Custom ASCII password, 0-16 bytes "
     "(自定义 ASCII 密码，0-16 字节)", PASSWORD_SOURCE_CUSTOM),
] + [
    (label, "preset:" + code)
    for label, code, _sid in KNOWN_PASSWORD_PRESETS
]
PASSWORD_SOURCE_BY_USER_OPTION = dict(PASSWORD_SOURCE_OPTIONS)

PROVISION_NONE = "none"
PROVISION_SUBSYSTEM_ONLY = "subsystem_only"
PROVISION_PASSWORD_AND_SUBSYSTEM = "password_and_subsystem"
PROVISION_ACTIONS = [
    ("No action (不执行)", PROVISION_NONE),
    ("Write subsystemID only (仅修改 subsystemID)",
     PROVISION_SUBSYSTEM_ONLY),
    ("Change programming password + subsystemID "
     "(修改读写频密码和 subsystemID)",
     PROVISION_PASSWORD_AND_SUBSYSTEM),
]

# Exact channel flag mapping recovered from CPS qH()/qb():
#
# byte 12:
#   bit 7: frequency hopping       0=off, 1=on
#   bit 6: unused/reserved
#   bit 5: unused/reserved
#   bit 4: scan add               0=yes, 1=no
#   bit 3: transmit power         0=low, 1=high
#   bit 2: bandwidth              0=wide, 1=narrow
#   bit 1: intercom mode          0=analog, 1=encrypted
#   bit 0: busy channel lockout   0=enabled, 1=disabled
#
# byte 13:
#   bits 0..4: encryption key 0..31
#   bits 5..7: preserved/reserved
FLAG_HOPPING = 0x80
FLAG_SCAN_EXCLUDED = 0x10
FLAG_HIGH_POWER = 0x08
FLAG_NARROW = 0x04
FLAG_ENCRYPTED_INTERCOM = 0x02
FLAG_BCL_DISABLED = 0x01
ENCRYPTION_KEY_MASK = 0x1F

INTERCOM_MODES = [
    "Analog Intercom (模拟对讲)",
    "Encrypted Intercom (加密对讲)",
]

ENCRYPTION_KEY_OPTIONS = [str(value) for value in range(32)]

# Protocol-A global/basic configuration blocks recovered from qH()/qb().
# Both blocks are part of the normal 0x03E0 clone image.
GENERAL_SETTINGS_OFFSET = 0x02B0
GENERAL_SETTINGS_SIZE = 0x10
SYSTEM_SETTINGS_OFFSET = 0x03C0
SYSTEM_SETTINGS_SIZE = 0x10

# 0x02B0 block, direct byte values used by the original CPS serializer.
GS_VOICE_SWITCH = 0
GS_LANGUAGE = 1
GS_SCAN_SWITCH = 2          # Hidden in this CPS build; preserved.
GS_VOX_STATE = 3
GS_VOX_GAIN = 4
GS_RX_DISABLE_VOX = 5       # Hidden in this CPS build; preserved.
GS_LOW_VOLTAGE_INHIBIT = 6
GS_HIGH_VOLTAGE_INHIBIT = 7
GS_ALARM_SWITCH = 8
GS_NOISE_REDUCTION = 9
GS_DOUBLE_WATCH_CHANNEL = 10  # Not used by protocol A; preserved.

# 0x03C0 block.
SS_FLAGS = 0
SS_SQUELCH = 1
SS_SIDE_KEY = 2
SS_TIMEOUT = 3
SS_BEEP = 0x01
SS_POWER_SAVE = 0x02
SS_ALARM_MODE = 0x04        # Not exposed for protocol A; preserved.

SQUELCH_OPTIONS = [
    ('Normally Open (常开)', 0),
    ('Normal (常规)', 1),
    ('Enhanced (加强)', 5),
    ('Strict (严格)', 9),
]

SIDE_KEY_OPTIONS = [
    ('Off (关)', 0),
    ('Monitor, long press (长按监听)', 1),
    ('High/Low Power (高低功率)', 2),
    ('Alarm (报警功能)', 3),
]

TIMEOUT_OPTIONS = [('Off (关)', 0)] + [
    ('%d seconds' % seconds, seconds // 30)
    for seconds in range(30, 301, 30)
]

# The tested version response uses language-combination 0, for which the CPS
# exposes English as value 0 and Chinese as value 1.
LANGUAGE_OPTIONS = [
    ('English (英文)', 0),
    ('Chinese (中文)', 1),
]


def _valid_or_default(value, allowed, default, label):
    if value in allowed:
        return value
    LOG.warning(
        '%s contains unsupported value 0x%02X; displaying default %r',
        label,
        value,
        default,
    )
    return default


def _set_flag(value, mask, enabled):
    return (value | mask) if enabled else (value & ~mask)

# In encrypted-intercom mode these standard CHIRP fields have no effect on
# the radio protocol. Keep the RX frequency itself editable, but prevent
# separate TX-frequency, tone, hopping and bandwidth edits.
ENCRYPTED_IMMUTABLE_FIELDS = [
    "duplex",
    "offset",
    "txfreq",          # Used when CHIRP's TX-frequency workflow is enabled.
    "tmode",
    "rtone",
    "ctone",
    "dtcs",
    "rx_dtcs",
    "dtcs_polarity",
    "cross_mode",
    "mode",
]


def _build_channel_extra(flags, encryption_key, encrypted):
    """Build CPS-specific columns and apply mode-dependent mutability."""
    extra = RadioSettingGroup("extra", "Extra")

    intercom_mode = RadioSetting(
        "intercom_mode",
        "Intercom Mode (对讲模式)",
        RadioSettingValueList(
            INTERCOM_MODES,
            current_index=1 if encrypted else 0,
        ),
    )
    intercom_mode.__doc__ = (
        "CPS field 对讲模式: 模拟对讲 or 加密对讲. "
        "Changing this value refreshes the row and enables only the fields "
        "that are meaningful for the selected mode."
    )
    extra.append(intercom_mode)

    encryption_key_setting = RadioSetting(
        "encryption_key",
        "Encryption Key (加密密钥)",
        RadioSettingValueList(
            ENCRYPTION_KEY_OPTIONS,
            current_index=encryption_key & ENCRYPTION_KEY_MASK,
        ),
    )
    encryption_key_setting.__doc__ = (
        "CPS field 加密密钥, range 0 through 31. It is editable only when "
        "对讲模式 is 加密对讲."
    )
    if not encrypted:
        encryption_key_setting.value.set_mutable(False)
    extra.append(encryption_key_setting)

    bcl = RadioSetting(
        "bcl",
        "Busy Lockout (繁忙锁定)",
        RadioSettingValueBoolean(not bool(flags & FLAG_BCL_DISABLED)),
    )
    bcl.__doc__ = (
        "CPS field 繁忙锁定. The stored bit is inverted: "
        "0 means enabled and 1 means disabled."
    )
    extra.append(bcl)

    hopping = RadioSetting(
        "hopping",
        "Frequency Hopping (跳频)",
        RadioSettingValueBoolean(bool(flags & FLAG_HOPPING)),
    )
    hopping.__doc__ = (
        "CPS field 跳频. It is editable only in 模拟对讲 mode."
    )
    if encrypted:
        hopping.value.set_mutable(False)
    extra.append(hopping)

    return extra


# CHIRP-next's global chirp_common.parse_freq() deliberately rejects MHz text
# with more than six fractional digits because CHIRP stores integral Hertz.
# The original CPS accepts longer decimal text and then snaps it to the nearest
# legal channel grid. Extend only that previously-invalid numeric-MHz case.
# All normal CHIRP inputs still use the unmodified upstream parser.
if not hasattr(chirp_common, "_888sd_original_parse_freq"):
    chirp_common._888sd_original_parse_freq = chirp_common.parse_freq

_ORIGINAL_PARSE_FREQ = chirp_common._888sd_original_parse_freq
_EXTENDED_MHZ_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")


def _parse_freq_with_long_decimal(freqstr):
    # CHIRP-next's frequency column converts an empty cell to integer 0
    # before calling chirp_common.parse_freq(). Upstream parse_freq() accepts
    # only strings and calls .strip(), so pass integral-Hz values through.
    if isinstance(freqstr, int):
        return freqstr

    try:
        return _ORIGINAL_PARSE_FREQ(freqstr)
    except ValueError:
        value = str(freqstr).strip()
        if not _EXTENDED_MHZ_RE.fullmatch(value):
            raise

        fraction = value.partition(".")[2]
        if len(fraction) <= 6:
            raise

        try:
            hz = Decimal(value) * Decimal(1_000_000)
        except InvalidOperation:
            raise

        # CHIRP has integral-Hz storage. Rounding here merely converts the
        # over-precise UI text into that representation; set_memory() then
        # applies the verified CPS 2.5/5/6.25-kHz nearest-grid rule.
        return int(hz.to_integral_value(rounding=ROUND_HALF_UP))


# Loading this experimental module extends only inputs that upstream CHIRP
# would otherwise reject. It does not alter parsing of any valid CHIRP input.
chirp_common.parse_freq = _parse_freq_with_long_decimal


# The official CPS accepts frequencies that are integer multiples of one of:
#   0.00250 MHz, 0.00500 MHz, 0.00625 MHz
# Keep the same order in the CHIRP feature declaration. 5 kHz is mathematically
# a subset of 2.5 kHz, but it is retained because it is an explicit CPS option.
CPS_TUNING_STEPS_KHZ = [2.5, 5.0, 6.25]
CPS_TUNING_STEPS_HZ = [2500, 5000, 6250]


def _frequency_is_supported(freq_hz):
    return any(freq_hz % step == 0 for step in CPS_TUNING_STEPS_HZ)


def _nearest_multiple(value, step):
    """Return the nearest integer multiple of step, with lower winning ties."""
    lower = (value // step) * step
    upper = lower + step
    if value - lower <= upper - value:
        return lower
    return upper


def _nearest_supported_frequency(freq_hz):
    """Apply the official CPS 2.5/5/6.25-kHz nearest-grid rule."""
    candidates = []
    for priority, step in enumerate(CPS_TUNING_STEPS_HZ):
        candidate = _nearest_multiple(freq_hz, step)
        candidates.append((abs(candidate - freq_hz), priority, candidate))
    return min(candidates)[2]


def _format_mhz(freq_hz):
    return '%.6f' % (freq_hz / 1_000_000.0)


def _password_blob(password_text):
    """Encode an independently selected programming password for the wire."""
    try:
        raw = str(password_text).encode("ascii")
    except UnicodeEncodeError as exc:
        raise errors.RadioError(
            "Programming password must contain ASCII characters only"
        ) from exc

    # Real-hardware verification confirms that an empty password is valid.
    # It is represented on the wire by the complete 16-byte field filled
    # with zero bytes.
    if len(raw) > 16:
        raise errors.RadioError(
            "Programming password must contain 0 to 16 ASCII bytes"
        )
    return raw.ljust(16, b"\x00")


def _dealer_password_text(dealer_code):
    """Generate the original CPS password text for a dealer preset."""
    try:
        raw = dealer_code.encode("ascii")
    except UnicodeEncodeError as exc:
        raise errors.RadioError("Dealer code must be ASCII") from exc

    # Matches btoa(encodeURIComponent(code)).substring(0, 16) for the
    # ASCII-only dealer codes present in these CPS tables.
    return base64.b64encode(raw).decode("ascii")[:16]


def _dealer_password_blob(dealer_code):
    """Convenience wrapper for an original-CPS dealer preset."""
    return _password_blob(_dealer_password_text(dealer_code))


def _subsystem_id_packet(subsystem_id):
    """Build 67 000004 + a uint8 subsystemID in the low byte."""
    if not 0 <= subsystem_id <= 0xFF:
        raise errors.RadioError(
            "subsystemID must be between 0 and 255"
        )
    return b"\x67\x00\x00\x04" + subsystem_id.to_bytes(4, "big")


def _parse_subsystem_id(value):
    text_value = str(value).strip()
    if not text_value or not text_value.isdigit():
        raise errors.RadioError("subsystemID must be a decimal integer")
    subsystem_id = int(text_value, 10)
    if not 0 <= subsystem_id <= 0xFF:
        raise errors.RadioError(
            "subsystemID must be between 0 and 255"
        )
    return subsystem_id


def _next_read_address(address):
    """Replicate the CPS protocol-A sparse read address sequence."""
    if address == 0x0108:
        return 0x02B0
    if address == 0x02B8:
        return 0x0330
    if address == 0x0338:
        return 0x0380
    return address + BLOCK_SIZE


def _next_write_address(address):
    """Replicate zH(address, 1), the CPS protocol-A write sequence.

    Unlike download, upload skips the read-only 0x0330 and 0x0338 blocks.
    """
    if address == 0x0108:
        return 0x02B0
    if address == 0x02B8:
        return 0x0380
    return address + BLOCK_SIZE


def _address_sequence(next_address):
    address = 0x0000
    addresses = []
    while address < IMAGE_SIZE:
        addresses.append(address)
        address = next_address(address)
    return addresses


READ_ADDRESSES = _address_sequence(_next_read_address)
WRITE_ADDRESSES = _address_sequence(_next_write_address)

# Guarded upload permits the complete channel area plus only the bytes whose
# basic-setting semantics are confirmed from the original CPS parser/serializer.
SAFE_CHANNEL_OFFSETS = set(range(
    CHANNEL_BASE,
    CHANNEL_BASE + CHANNEL_COUNT * CHANNEL_SIZE,
))
SAFE_GLOBAL_OFFSETS = {
    GENERAL_SETTINGS_OFFSET + GS_VOICE_SWITCH,
    GENERAL_SETTINGS_OFFSET + GS_LANGUAGE,
    GENERAL_SETTINGS_OFFSET + GS_VOX_STATE,
    GENERAL_SETTINGS_OFFSET + GS_VOX_GAIN,
    GENERAL_SETTINGS_OFFSET + GS_LOW_VOLTAGE_INHIBIT,
    GENERAL_SETTINGS_OFFSET + GS_HIGH_VOLTAGE_INHIBIT,
    GENERAL_SETTINGS_OFFSET + GS_ALARM_SWITCH,
    GENERAL_SETTINGS_OFFSET + GS_NOISE_REDUCTION,
    SYSTEM_SETTINGS_OFFSET + SS_FLAGS,
    SYSTEM_SETTINGS_OFFSET + SS_SQUELCH,
    SYSTEM_SETTINGS_OFFSET + SS_SIDE_KEY,
    SYSTEM_SETTINGS_OFFSET + SS_TIMEOUT,
}
SAFE_EDIT_OFFSETS = SAFE_CHANNEL_OFFSETS | SAFE_GLOBAL_OFFSETS


def _bcd_byte_valid(value):
    return (value & 0x0F) <= 9 and ((value >> 4) & 0x0F) <= 9


def _decode_frequency(raw):
    """Decode four-byte little-endian packed BCD in 10-Hz units."""
    if raw in (b"\x00" * 4, b"\xFF" * 4):
        return 0

    if len(raw) != 4 or not all(_bcd_byte_valid(x) for x in raw):
        raise ValueError("Invalid frequency BCD: %s" % util.hexprint(raw))

    digits = "".join("%02X" % byte for byte in reversed(raw))
    return int(digits, 10) * 10


def _encode_frequency(freq_hz):
    """Encode Hertz as four-byte little-endian packed BCD."""
    if not 0 <= freq_hz <= 999_999_990:
        raise ValueError("Frequency is outside the 4-byte BCD range")

    units_10hz = int(round(freq_hz / 10.0))
    digits = "%08d" % units_10hz
    packed = bytes(int(digits[i:i + 2], 16) for i in range(0, 8, 2))
    return packed[::-1]


def _decode_tone(raw):
    """Return (mode, value, polarity) for the two-byte tone field."""
    if raw in (b"\x00\x00", b"\xFF\xFF"):
        return "", None, "N"

    if len(raw) != 2:
        raise ValueError("Tone field must be two bytes")

    word = (raw[1] << 8) | raw[0]

    # CPS treats bit 15 as DCS and bit 14 as inverted polarity.
    if word & 0x8000:
        digits = "%03X" % (word & 0x0FFF)
        if any(ch not in "0123456789" for ch in digits):
            raise ValueError("Invalid DCS BCD: %s" % util.hexprint(raw))
        return "DTCS", int(digits, 10), "R" if word & 0x4000 else "N"

    digits = "%04X" % word
    if any(ch not in "0123456789" for ch in digits):
        raise ValueError("Invalid CTCSS BCD: %s" % util.hexprint(raw))
    return "Tone", int(digits, 10) / 10.0, "N"


def _encode_tone(mode, value, polarity="N"):
    if not mode:
        return b"\xFF\xFF"

    if mode == "Tone":
        digits = "%04d" % int(round(float(value) * 10))
        word = int(digits, 16)
    elif mode == "DTCS":
        digits = "%03d" % int(value)
        word = 0x8000 | int(digits, 16)
        if polarity == "R":
            word |= 0x4000
    else:
        raise ValueError("Unsupported tone mode %r" % mode)

    return struct.pack("<H", word)


def _apply_tones_to_memory(mem, tx_tone, rx_tone):
    tx_mode, tx_value, tx_pol = tx_tone
    rx_mode, rx_value, rx_pol = rx_tone

    mem.dtcs_polarity = tx_pol + rx_pol

    if tx_mode == "Tone":
        mem.rtone = tx_value
    elif tx_mode == "DTCS":
        mem.dtcs = tx_value

    if rx_mode == "Tone":
        mem.ctone = rx_value
    elif rx_mode == "DTCS":
        mem.rx_dtcs = rx_value

    if tx_mode == "Tone" and not rx_mode:
        mem.tmode = "Tone"
    elif (
        tx_mode == "Tone"
        and rx_mode == "Tone"
        and tx_value == rx_value
    ):
        mem.tmode = "TSQL"
    elif (
        tx_mode == "DTCS"
        and rx_mode == "DTCS"
        and tx_value == rx_value
    ):
        mem.tmode = "DTCS"
    elif tx_mode or rx_mode:
        mem.tmode = "Cross"
        mem.cross_mode = "%s->%s" % (tx_mode, rx_mode)
    else:
        mem.tmode = ""


def _tones_from_memory(mem):
    tx_mode = ""
    rx_mode = ""
    tx_value = None
    rx_value = None

    if mem.tmode == "Tone":
        tx_mode = "Tone"
        tx_value = mem.rtone
    elif mem.tmode == "TSQL":
        tx_mode = rx_mode = "Tone"
        tx_value = rx_value = mem.ctone
    elif mem.tmode == "DTCS":
        tx_mode = rx_mode = "DTCS"
        tx_value = rx_value = mem.dtcs
    elif mem.tmode == "Cross":
        tx_mode, rx_mode = mem.cross_mode.split("->", 1)
        if tx_mode == "Tone":
            tx_value = mem.rtone
        elif tx_mode == "DTCS":
            tx_value = mem.dtcs

        if rx_mode == "Tone":
            rx_value = mem.ctone
        elif rx_mode == "DTCS":
            rx_value = mem.rx_dtcs

    tx_pol = mem.dtcs_polarity[0] if mem.dtcs_polarity else "N"
    rx_pol = mem.dtcs_polarity[1] if mem.dtcs_polarity else "N"

    return (
        (tx_mode, tx_value, tx_pol),
        (rx_mode, rx_value, rx_pol),
    )


class _Protocol:
    def __init__(self, radio):
        self.radio = radio
        self.pipe = radio.pipe

    def _write(self, data):
        LOG.debug("TX: %s", util.hexprint(data))
        try:
            self.pipe.write(data)
        except Exception as exc:
            raise errors.RadioError("Failed to write to the radio") from exc

    def _read_exact(self, count, label):
        try:
            data = self.pipe.read(count)
        except Exception as exc:
            raise errors.RadioError(
                "Serial read failed during %s" % label
            ) from exc

        LOG.debug("RX %s: %s", label, util.hexprint(data or b""))
        if not data:
            raise errors.RadioError("No response during %s" % label)
        if len(data) != count:
            raise errors.RadioError(
                "Short response during %s: expected %d, got %d"
                % (label, count, len(data))
            )
        return data

    def _expect_ack(self, payload, label):
        self._write(payload)
        reply = self._read_exact(1, label)
        if reply == REJECT:
            raise errors.RadioError("%s was explicitly rejected" % label)
        if reply != ACK:
            raise errors.RadioError(
                "%s returned unexpected response %s"
                % (label, util.hexprint(reply))
            )

    def _flush_input(self):
        original_timeout = self.pipe.timeout
        try:
            self.pipe.timeout = 0.01
            junk = self.pipe.read(256)
            if junk:
                LOG.debug(
                    "Discarded %d stale byte(s): %s",
                    len(junk),
                    util.hexprint(junk),
                )
        finally:
            self.pipe.timeout = original_timeout

    def _probe_program(self, label, attempts=3):
        """Send the CPS prOGRAM probe and return its four-byte reply."""
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                self._write(PROGRAM_PROBE)
                version = self._read_exact(
                    4, "%s attempt %d" % (label, attempt)
                )
                LOG.info(
                    "%s response: %s", label, util.hexprint(version)
                )
                return version
            except errors.RadioError as exc:
                last_error = exc
                LOG.debug(
                    "%s attempt %d failed: %s", label, attempt, exc
                )
                self._flush_input()
                time.sleep(0.2)

        raise errors.RadioError(
            "Radio did not answer %s" % label
        ) from last_error

    def initialize(self):
        self.pipe.baudrate = 9600
        self.pipe.parity = "N"
        self.pipe.bytesize = 8
        self.pipe.stopbits = 1
        self.pipe.timeout = 1.0

        self._flush_input()
        time.sleep(0.9)
        return self._probe_program("initial programming/version probe")

    def restart_program_session(self):
        """Replicate M('start') from the original CPS after password auth."""
        return self._probe_program(
            "post-auth programming/version probe",
            attempts=3,
        )

    def authenticate_normal(self, password_blob):
        self._expect_ack(
            NORMAL_PASSWORD_ENTRY,
            "normal password entry",
        )
        self._expect_ack(
            AUTH_HANDSHAKE,
            "normal password handshake",
        )
        self._expect_ack(
            password_blob,
            "normal programming password",
        )

    def enter_clone_read(self):
        self._expect_ack(CLONE_MAGIC, "clone read entry")

        self._write(b"\x02")
        ident = self._read_exact(8, "clone identification")
        if ident != CLONE_IDENT:
            raise errors.RadioError(
                "Unexpected clone identification: %s"
                % util.hexprint(ident)
            )

        self._expect_ack(ACK, "clone identification acknowledgement")

        self._write(CLONE_PROBE)
        reply = self._read_exact(12, "clone probe block")
        if reply != CLONE_PROBE_REPLY:
            raise errors.RadioError(
                "Unexpected clone probe reply: %s"
                % util.hexprint(reply)
            )

        self._expect_ack(ACK, "clone probe acknowledgement")

    def read_block(self, address):
        request = struct.pack(">BHB", ord("R"), address, BLOCK_SIZE)
        self._write(request)
        response = self._read_exact(
            4 + BLOCK_SIZE,
            "read block 0x%04X" % address,
        )

        # The 0x0130 probe uses the documented/standard response header:
        #
        #     57 <addr:be16> 08 <8 data bytes>
        #
        # However, the tested 888SD returns normal data blocks with a
        # different four-byte prefix.  At address 0x0000 it returned:
        #
        #     08 00 00 52 <8 data bytes>
        #
        # which is the request header (52 00 00 08) in reverse order.
        # The official CPS deliberately does not validate normal block
        # headers; it simply discards the first four bytes and consumes the
        # following eight bytes.  Match that verified behavior here.
        header = response[:4]
        standard_header = struct.pack(
            ">BHB", ord("W"), address, BLOCK_SIZE
        )
        reversed_request_header = request[::-1]

        if header == standard_header:
            LOG.debug(
                "Block 0x%04X used standard response header %s",
                address,
                util.hexprint(header),
            )
        elif header == reversed_request_header:
            LOG.debug(
                "Block 0x%04X used reversed-request header %s",
                address,
                util.hexprint(header),
            )
        else:
            LOG.warning(
                "Block 0x%04X used unrecognized four-byte header %s; "
                "following official CPS behavior and accepting its "
                "eight-byte payload",
                address,
                util.hexprint(header),
            )

        self._expect_ack(ACK, "acknowledge block 0x%04X" % address)
        return response[4:]

    def enter_clone_write(self):
        """Transition from the CPS read-style handshake into write mode."""
        self._write(CMD_EXIT)
        reply = self._read_exact(1, "clone write transition")
        if reply != WRITE_TRANSITION_REPLY:
            raise errors.RadioError(
                "Expected 46 while entering write mode, got %s"
                % util.hexprint(reply)
            )

        # The original CPS then enters protocol-A clone mode a second time.
        self._expect_ack(CLONE_MAGIC, "clone write entry")

        self._write(b"\x02")
        ident = self._read_exact(8, "write-mode clone identification")
        if ident != CLONE_IDENT:
            raise errors.RadioError(
                "Unexpected write-mode identification: %s"
                % util.hexprint(ident)
            )

        self._expect_ack(
            ACK,
            "write-mode identification acknowledgement",
        )

    def write_block(self, address, data):
        if len(data) != BLOCK_SIZE:
            raise errors.RadioError(
                "Write block 0x%04X must contain exactly %d bytes"
                % (address, BLOCK_SIZE)
            )

        packet = (
            struct.pack(">BHB", ord("W"), address, BLOCK_SIZE)
            + bytes(data)
        )
        self._expect_ack(packet, "write block 0x%04X" % address)

    def write_subsystem_id_only(self, current_password_blob, subsystem_id):
        """Use the CPS restore-subnet path without changing the password."""
        self.initialize()
        self.authenticate_normal(current_password_blob)
        self._expect_ack(CONFIG_ENTRY, "subsystem configuration entry")
        self._expect_ack(CONFIG_CONFIRM, "subsystem configuration confirm")
        self._expect_ack(
            _subsystem_id_packet(subsystem_id),
            "write subsystemID %d" % subsystem_id,
        )
        self._expect_ack(CMD_EXIT, "subsystem configuration exit")

    def change_password_and_subsystem(self, new_password_text, subsystem_id):
        """Run the verified hidden super-administrator eight-step flow."""
        self.initialize()
        self._expect_ack(SUPERADMIN_ENTRY, "super-administrator entry")
        self._expect_ack(
            PASSWORD_CHANGE_COMMAND,
            "password-change operation select",
        )
        self._expect_ack(
            SUPERADMIN_PASSWORD,
            "super-administrator old password",
        )
        self._expect_ack(
            _password_blob(new_password_text),
            "new normal programming password",
        )
        self._expect_ack(CONFIG_ENTRY, "post-password configuration entry")
        self._expect_ack(CONFIG_CONFIRM, "post-password configuration confirm")
        self._expect_ack(
            _subsystem_id_packet(subsystem_id),
            "write subsystemID %d" % subsystem_id,
        )
        self._expect_ack(CMD_EXIT, "password/subsystem provisioning exit")

    def exit(self):
        try:
            self._write(CMD_EXIT)
        except errors.RadioError:
            LOG.exception("Failed to send clone exit command")


def _download(radio):
    protocol = _Protocol(radio)
    protocol.initialize()
    protocol.authenticate_normal(radio._current_password_blob())

    # The original CPS starts a fresh prOGRAM session after the normal
    # password has been accepted. Omitting this reset lets the handshake
    # appear to succeed but shifts/mangles the first clone block reply.
    protocol.restart_program_session()
    protocol.enter_clone_read()

    image = bytearray(b"\xFF" * IMAGE_SIZE)

    status = chirp_common.Status()
    status.cur = 0
    status.max = len(READ_ADDRESSES)
    status.msg = "Cloning from 888SD..."

    try:
        for index, address in enumerate(READ_ADDRESSES, start=1):
            image[address:address + BLOCK_SIZE] = protocol.read_block(address)
            status.cur = index
            radio.status_fn(status)
    finally:
        protocol.exit()

    return memmap.MemoryMapBytes(bytes(image))


def _upload(radio):
    protocol = _Protocol(radio)
    protocol.initialize()
    protocol.authenticate_normal(radio._current_password_blob())
    protocol.restart_program_session()

    # The original CPS performs the complete read-style clone handshake,
    # including the 0x0130 all-FF probe, before transitioning to write mode.
    protocol.enter_clone_read()
    protocol.enter_clone_write()

    image = radio._mmap.get_packed()

    status = chirp_common.Status()
    status.cur = 0
    status.max = len(WRITE_ADDRESSES)
    status.msg = "Cloning to 888SD..."

    try:
        for index, address in enumerate(WRITE_ADDRESSES, start=1):
            block = image[address:address + BLOCK_SIZE]
            protocol.write_block(address, block)
            status.cur = index
            radio.status_fn(status)
    finally:
        # The original CPS sends 45 after the final ACK and does not require
        # a response for this last exit operation.
        protocol.exit()


@directory.register
class Baofeng888SDRadio(
    chirp_common.CloneModeRadio,
    chirp_common.ExperimentalRadio,
):
    """Baofeng 888SD-class GMSK 16-channel radio."""

    VENDOR = "Baofeng"
    MODEL = "888SD (GMSK)"
    VARIANT = "CN59500 / 宝锋 / provisioning v0.18"

    BAUD_RATE = 9600
    NEEDS_COMPAT_SERIAL = False

    DEALER_CODE = DEFAULT_DEALER_CODE
    DEFAULT_SUBSYSTEM_ID = 1

    @classmethod
    def match_model(cls, filedata, filename):
        return len(filedata) == IMAGE_SIZE

    def _current_password_text(self):
        return getattr(
            self,
            "_programming_password_text_override",
            _dealer_password_text(self.DEALER_CODE),
        )

    def _current_password_blob(self):
        return _password_blob(self._current_password_text())

    def _password_text_for_source(self, source, custom_password=None):
        """Resolve one UI password source to the effective password text."""
        if source == PASSWORD_SOURCE_KEEP:
            return self._current_password_text()
        if source == PASSWORD_SOURCE_EMPTY:
            return ""
        if source == PASSWORD_SOURCE_CUSTOM:
            if custom_password is not None:
                return custom_password
            return getattr(
                self,
                "_provision_custom_password",
                self._current_password_text(),
            )
        if source.startswith("preset:"):
            code = source.split(":", 1)[1]
            if code not in KNOWN_PRESET_BY_CODE:
                raise errors.RadioError(
                    "Unknown programming-password preset %s" % code
                )
            return _dealer_password_text(code)
        raise errors.RadioError(
            "Unknown programming-password source %r" % source
        )

    def _resolve_target_password_text(self):
        source = getattr(
            self,
            "_provision_password_source",
            PASSWORD_SOURCE_KEEP,
        )
        return self._password_text_for_source(source)

    def get_features(self):
        features = chirp_common.RadioFeatures()
        features.has_bank = False
        features.has_name = False
        features.has_settings = True
        features.has_tuning_step = False
        features.can_odd_split = True
        features.has_offset = True
        features.has_mode = True
        features.has_dtcs = True
        features.has_rx_dtcs = True
        features.has_dtcs_polarity = True
        features.has_ctone = True
        features.has_cross = True

        features.memory_bounds = (1, CHANNEL_COUNT)
        features.valid_bands = [(400_000_000, 480_000_000)]
        features.valid_modes = ["FM", "NFM"]
        # Match the official CPS prompt exactly: frequencies must be an
        # integer multiple of 2.50, 5.00, or 6.25 kHz.
        features.valid_tuning_steps = list(CPS_TUNING_STEPS_KHZ)
        features.valid_power_levels = POWER_LEVELS
        features.valid_skips = ["", "S"]
        features.valid_tmodes = ["", "Tone", "TSQL", "DTCS", "Cross"]
        features.valid_cross_modes = [
            "Tone->Tone",
            "DTCS->",
            "->DTCS",
            "Tone->DTCS",
            "DTCS->Tone",
            "->Tone",
            "DTCS->DTCS",
        ]
        features.valid_dtcs_codes = chirp_common.DTCS_CODES
        return features

    def sync_in(self):
        try:
            self._mmap = _download(self)
            self._live_download_baseline = self._mmap.get_packed()
            self.process_mmap()
        except errors.RadioError:
            raise
        except Exception as exc:
            LOG.exception("Unexpected failure while downloading the 888SD")
            raise errors.RadioError(
                "Unexpected error communicating with the 888SD"
            ) from exc

    def _validate_guarded_upload(self):
        baseline = getattr(self, "_live_download_baseline", None)
        if baseline is None:
            raise errors.RadioError(
                "Guarded upload requires a live Download From Radio in "
                "this same CHIRP session. Saved or externally loaded images "
                "cannot be uploaded with experimental driver v0.18."
            )

        current = self._mmap.get_packed()
        if len(current) != IMAGE_SIZE or len(baseline) != IMAGE_SIZE:
            raise errors.RadioError(
                "Unexpected image size; refusing guarded upload"
            )

        changed = [
            offset
            for offset, (old, new) in enumerate(zip(baseline, current))
            if old != new
        ]
        unsafe = [
            offset
            for offset in changed
            if offset not in SAFE_EDIT_OFFSETS
        ]
        if unsafe:
            preview = ", ".join("0x%04X" % x for x in unsafe[:12])
            if len(unsafe) > 12:
                preview += ", ..."
            raise errors.RadioError(
                "Experimental v0.18 refuses changes outside verified "
                "channel/basic-setting bytes. Unsafe changed offsets: %s"
                % preview
            )

        LOG.info(
            "Guarded upload accepted: %d changed verified byte(s)",
            len(changed),
        )
        if changed:
            LOG.debug(
                "Changed verified offsets: %s",
                ", ".join("0x%04X" % x for x in changed),
            )
        else:
            LOG.info("Guarded upload is an exact no-op image rewrite")

        return changed

    def _run_pending_provisioning(self):
        action = getattr(self, '_provision_action', PROVISION_NONE)
        if action == PROVISION_NONE:
            return

        if not getattr(self, '_provision_confirmed', False):
            raise errors.RadioError(
                "Provisioning was selected but the confirmation checkbox "
                "was not enabled"
            )

        subsystem_id = _parse_subsystem_id(
            getattr(
                self,
                '_provision_subsystem_id',
                str(self.DEFAULT_SUBSYSTEM_ID),
            )
        )
        target_password_text = self._resolve_target_password_text()

        # The original CPS waits after leaving the normal clone/write state
        # before entering the independent provisioning state machine.
        time.sleep(1.0)
        protocol = _Protocol(self)

        if action == PROVISION_SUBSYSTEM_ONLY:
            protocol.write_subsystem_id_only(
                self._current_password_blob(),
                subsystem_id,
            )
            LOG.info("subsystemID changed to %d", subsystem_id)
        elif action == PROVISION_PASSWORD_AND_SUBSYSTEM:
            protocol.change_password_and_subsystem(
                target_password_text,
                subsystem_id,
            )
            # Keep this live CHIRP instance usable after successful migration.
            self._programming_password_text_override = target_password_text
            LOG.info(
                "Programming password changed and subsystemID changed to %d",
                subsystem_id,
            )
        else:
            raise errors.RadioError(
                "Unknown provisioning action %r" % action
            )

        # Provisioning actions are one-shot.
        self._provision_action = PROVISION_NONE
        self._provision_confirmed = False

    def sync_out(self):
        try:
            changed = self._validate_guarded_upload()

            # Do not rewrite all clone blocks when the user selected only an
            # out-of-band password/subsystem operation.
            if changed:
                _upload(self)
                self._live_download_baseline = self._mmap.get_packed()
            else:
                LOG.info("No clone-image changes; skipping normal block upload")

            self._run_pending_provisioning()
        except errors.RadioError:
            raise
        except Exception as exc:
            LOG.exception("Unexpected failure while uploading the 888SD")
            raise errors.RadioError(
                "Unexpected error writing to the 888SD"
            ) from exc

    def process_mmap(self):
        # The first implementation uses explicit byte decoding rather than
        # chirp.bitwise so every byte remains easy to compare with the CPS.
        if self._mmap is None:
            return

    def _channel_raw(self, number):
        if not 1 <= number <= CHANNEL_COUNT:
            raise errors.InvalidMemoryLocation(
                "Memory must be between 1 and %d" % CHANNEL_COUNT
            )
        offset = CHANNEL_BASE + (number - 1) * CHANNEL_SIZE
        return offset, bytes(self._mmap[offset:offset + CHANNEL_SIZE])

    def get_raw_memory(self, number):
        offset, raw = self._channel_raw(number)
        return "0x%04X: %s" % (offset, util.hexprint(raw))

    def get_memory(self, number):
        _offset, raw = self._channel_raw(number)

        memory = chirp_common.Memory()
        memory.number = number

        if raw[:4] in (b"\x00" * 4, b"\xFF" * 4):
            # Do not expose the all-FF erased record as meaningful defaults.
            # A newly-created channel should begin as the CPS would present it:
            # analog intercom, encryption key 0, hopping off, BCL off, high power.
            memory.empty = True
            memory.freq = 0
            memory.duplex = ""
            memory.offset = 0
            memory.tmode = ""
            memory.mode = "FM"
            memory.tuning_step = CPS_TUNING_STEPS_KHZ[0]
            memory.skip = ""
            memory.power = POWER_LEVELS[1]
            memory.extra = _build_channel_extra(
                # BCL is stored inverted: bit set means disabled/off.
                flags=FLAG_BCL_DISABLED,
                encryption_key=0,
                encrypted=False,
            )
            return memory

        try:
            rx_freq = _decode_frequency(raw[0:4])
            tx_freq = _decode_frequency(raw[4:8])
            rx_tone = _decode_tone(raw[8:10])
            tx_tone = _decode_tone(raw[10:12])
        except ValueError as exc:
            raise errors.RadioError(
                "Invalid channel %d data: %s" % (number, exc)
            ) from exc

        memory.freq = rx_freq
        # The tuning-step column is hidden for this fixed-channel radio, but
        # CHIRP still validates the Memory object after every cell edit.
        # Populate a valid value matching the current frequency.
        try:
            memory.tuning_step = chirp_common.required_step(
                rx_freq,
                CPS_TUNING_STEPS_KHZ,
            )
        except errors.InvalidDataError:
            # A non-CPS frequency may exist in an imported/edited image. Keep a
            # legal placeholder; validate_memory() will warn and set_memory()
            # will snap it to the nearest official grid.
            memory.tuning_step = CPS_TUNING_STEPS_KHZ[0]

        if tx_freq == 0:
            memory.duplex = "off"
            memory.offset = 0
        elif tx_freq == rx_freq:
            memory.duplex = ""
            memory.offset = 0
        else:
            difference = tx_freq - rx_freq
            if chirp_common.is_split(
                self.get_features().valid_bands,
                rx_freq,
                tx_freq,
            ):
                memory.duplex = "split"
                memory.offset = tx_freq
            elif difference > 0:
                memory.duplex = "+"
                memory.offset = difference
            else:
                memory.duplex = "-"
                memory.offset = abs(difference)

        _apply_tones_to_memory(memory, tx_tone, rx_tone)

        flags = raw[12]
        memory.skip = "S" if flags & FLAG_SCAN_EXCLUDED else ""
        memory.power = (POWER_LEVELS[1] if flags & FLAG_HIGH_POWER else POWER_LEVELS[0])
        memory.mode = "NFM" if flags & FLAG_NARROW else "FM"

        encrypted = bool(flags & FLAG_ENCRYPTED_INTERCOM)
        memory.extra = _build_channel_extra(
            flags=flags,
            encryption_key=raw[13] & ENCRYPTION_KEY_MASK,
            encrypted=encrypted,
        )

        if encrypted:
            memory.immutable = list(ENCRYPTED_IMMUTABLE_FIELDS)

        return memory

    def validate_memory(self, memory):
        """Use CHIRP validation, but emulate the CPS nearest-grid behavior."""
        # Clearing the frequency cell is CHIRP-next's normal erase gesture.
        # At this stage memory.empty is still False, but freq has become 0.
        # Treat it as a valid pending deletion instead of validating 0 Hz.
        if not memory.freq:
            return []

        messages = super().validate_memory(memory)
        filtered = []

        for message in messages:
            # CHIRP normally blocks an edit before set_memory() if no declared
            # step reaches the RX frequency. The official CPS instead warns
            # and automatically replaces it with the closest legal value.
            if (
                isinstance(message, chirp_common.ValidationError)
                and str(message).startswith(
                    'Unable to find a supported tuning step for '
                )
            ):
                continue
            filtered.append(message)

        if memory.freq and not _frequency_is_supported(memory.freq):
            nearest = _nearest_supported_frequency(memory.freq)
            filtered.append(
                chirp_common.ValidationWarning(
                    'Frequency must be an integer multiple of 0.00250, '
                    '0.00500, or 0.00625 MHz; it will be adjusted from %s '
                    'to the nearest supported frequency %s MHz.'
                    % (_format_mhz(memory.freq), _format_mhz(nearest))
                )
            )

        return filtered

    def _settings_blocks(self):
        packed = self._mmap.get_packed()
        general = bytearray(packed[
            GENERAL_SETTINGS_OFFSET:
            GENERAL_SETTINGS_OFFSET + GENERAL_SETTINGS_SIZE
        ])
        system = bytearray(packed[
            SYSTEM_SETTINGS_OFFSET:
            SYSTEM_SETTINGS_OFFSET + SYSTEM_SETTINGS_SIZE
        ])
        return general, system

    def get_settings(self):
        """Expose the visible Protocol-A basic settings from the CPS."""
        general, system = self._settings_blocks()

        basic = RadioSettingGroup(
            'basic',
            'Basic Configuration (基础配置)',
        )
        audio = RadioSettingGroup(
            'audio',
            'Audio and Language (语音与语言)',
        )
        vox = RadioSettingGroup(
            'vox',
            'VOX',
        )
        power = RadioSettingGroup(
            'power',
            'Power Settings (电源设置)',
        )
        provisioning = RadioSettingGroup(
            'provisioning',
            'Provisioning (密码与 subsystemID)',
        )

        squelch = _valid_or_default(
            system[SS_SQUELCH],
            {entry[1] for entry in SQUELCH_OPTIONS},
            1,
            'Squelch',
        )
        basic.append(RadioSetting(
            'squelch',
            'Squelch Level (静噪级别)',
            RadioSettingValueMap(SQUELCH_OPTIONS, mem_val=squelch),
        ))

        side_key = _valid_or_default(
            system[SS_SIDE_KEY],
            {entry[1] for entry in SIDE_KEY_OPTIONS},
            1,
            'Side key',
        )
        basic.append(RadioSetting(
            'side_key',
            'Side Key (侧键选择)',
            RadioSettingValueMap(SIDE_KEY_OPTIONS, mem_val=side_key),
        ))

        timeout = _valid_or_default(
            system[SS_TIMEOUT],
            {entry[1] for entry in TIMEOUT_OPTIONS},
            4,
            'Transmit timeout',
        )
        basic.append(RadioSetting(
            'timeout',
            'Transmit Timeout (发射超时)',
            RadioSettingValueMap(TIMEOUT_OPTIONS, mem_val=timeout),
        ))

        basic.append(RadioSetting(
            'alarm_switch',
            'Alarm Switch (报警开关)',
            RadioSettingValueBoolean(bool(general[GS_ALARM_SWITCH])),
        ))
        basic.append(RadioSetting(
            'noise_reduction',
            'Noise Reduction (降噪开关)',
            RadioSettingValueBoolean(bool(general[GS_NOISE_REDUCTION])),
        ))

        language = _valid_or_default(
            general[GS_LANGUAGE],
            {0, 1},
            1,
            'Language',
        )
        audio.append(RadioSetting(
            'language',
            'Language (语言选择)',
            RadioSettingValueMap(LANGUAGE_OPTIONS, mem_val=language),
        ))

        # These are two independent settings:
        #   voice_switch: spoken voice announcements, such as startup/channel
        #                 prompts ("语音开关")
        #   beep:         short operation/key beep tones ("提示音")
        #
        # They are stored and written independently:
        #   0x02B0 byte 0 = spoken voice announcement switch
        #   0x03C0 bit 0  = beep tone switch
        audio.append(RadioSetting(
            'voice_switch',
            'Spoken Voice Prompt (语音开关)',
            RadioSettingValueBoolean(bool(general[GS_VOICE_SWITCH])),
        ))
        audio.append(RadioSetting(
            'beep',
            'Beep Tone (提示音)',
            RadioSettingValueBoolean(bool(system[SS_FLAGS] & SS_BEEP)),
        ))

        vox_enabled = bool(general[GS_VOX_STATE])
        vox.append(RadioSetting(
            'vox_enabled',
            'VOX Enable (VOX功能)',
            RadioSettingValueBoolean(vox_enabled),
        ))
        vox_gain = _valid_or_default(
            general[GS_VOX_GAIN],
            set(range(1, 6)),
            1,
            'VOX gain',
        )
        vox.append(RadioSetting(
            'vox_gain',
            'VOX Gain (VOX增益电平)',
            RadioSettingValueInteger(1, 5, vox_gain),
        ))

        power.append(RadioSetting(
            'power_save',
            'Battery Save (省电功能)',
            RadioSettingValueBoolean(
                bool(system[SS_FLAGS] & SS_POWER_SAVE)
            ),
        ))
        power.append(RadioSetting(
            'low_voltage_inhibit',
            'Low Voltage TX Inhibit (低电禁止发射)',
            RadioSettingValueBoolean(
                bool(general[GS_LOW_VOLTAGE_INHIBIT])
            ),
        ))
        power.append(RadioSetting(
            'high_voltage_inhibit',
            'High Voltage TX Inhibit (高电禁止发射)',
            RadioSettingValueBoolean(
                bool(general[GS_HIGH_VOLTAGE_INHIBIT])
            ),
        ))

        current_profile = RadioSetting(
            'current_dealer_code',
            'Current Connection Preset (当前连接预设)',
            RadioSettingValueString(
                1,
                16,
                self.DEALER_CODE,
                autopad=False,
                charset=chirp_common.CHARSET_ASCII,
            ),
        )
        current_profile.value.set_mutable(False)
        current_profile.__doc__ = (
            'This identifies the preset selected in the Download From Radio '
            'dialog. It is only a convenience label and is not read from '
            'the device.'
        )
        provisioning.append(current_profile)

        current_password = RadioSetting(
            'current_password_text',
            'Current Programming Password (当前读写频密码)',
            RadioSettingValueString(
                0,
                16,
                self._current_password_text(),
                autopad=False,
                charset=chirp_common.CHARSET_ASCII,
            ),
        )
        current_password.value.set_mutable(False)
        current_password.__doc__ = (
            'Actual ASCII password bytes used by ucbfpwd before zero padding. An empty value means the verified 16-byte all-zero password.'
        )
        provisioning.append(current_password)

        password_source = getattr(
            self,
            '_provision_password_source',
            PASSWORD_SOURCE_KEEP,
        )
        if password_source not in {
            item[1] for item in PASSWORD_SOURCE_OPTIONS
        }:
            password_source = PASSWORD_SOURCE_KEEP

        # Preserve the last actual custom entry while the user temporarily
        # selects a preset. The visible field shows the effective password for
        # every source, but only Custom is editable.
        custom_password_cache = [
            getattr(
                self,
                '_provision_custom_password',
                self._current_password_text(),
            )
        ]
        _password_blob(custom_password_cache[0])

        effective_password = self._password_text_for_source(
            password_source,
            custom_password_cache[0],
        )
        custom_password_setting = RadioSetting(
            'custom_password',
            'Effective New Password / Custom Input '
            '(实际新密码 / 自定义输入)',
            RadioSettingValueString(
                0,
                16,
                effective_password,
                autopad=False,
                charset=chirp_common.CHARSET_ASCII,
            ),
        )
        custom_password_setting.value.set_mutable(
            password_source == PASSWORD_SOURCE_CUSTOM
        )
        custom_password_setting.__doc__ = (
            'This field always displays the actual 0-16 byte ASCII password '
            'that will be written. It is editable only when New Password '
            'Source is Custom ASCII. Dealer presets are Base64-derived here; '
            'Empty Password is displayed as an empty read-only value and is '
            'written as sixteen zero bytes.'
        )

        password_source_value = RadioSettingValueMap(
            PASSWORD_SOURCE_OPTIONS,
            mem_val=password_source,
        )
        password_source_setting = RadioSetting(
            'password_source',
            'New Password Source (新密码来源)',
            password_source_value,
        )

        def _validate_password_source(user_option):
            """Synchronize effective password and custom-field mutability."""
            source = PASSWORD_SOURCE_BY_USER_OPTION[user_option]
            value = custom_password_setting.value

            # Cache the user's custom text before leaving Custom mode.
            current_source = password_source_value.get_mem_val()
            if current_source == PASSWORD_SOURCE_CUSTOM:
                custom_password_cache[0] = str(value)
                _password_blob(custom_password_cache[0])

            if source == PASSWORD_SOURCE_CUSTOM:
                display_password = custom_password_cache[0]
            else:
                display_password = self._password_text_for_source(
                    source,
                    custom_password_cache[0],
                )

            # A read-only RadioSettingValue rejects set_value(), so temporarily
            # unlock it while replacing the displayed effective password.
            value.set_mutable(True)
            value.set_value(display_password)
            value.set_mutable(source == PASSWORD_SOURCE_CUSTOM)
            return user_option

        # CHIRP invokes the validation callback whenever the map value changes.
        # This lets the sibling password value follow the selected source.
        password_source_value.set_validate_callback(
            _validate_password_source
        )

        provisioning.append(password_source_setting)
        provisioning.append(custom_password_setting)

        subsystem_value = _parse_subsystem_id(getattr(
            self,
            '_provision_subsystem_id',
            self.DEFAULT_SUBSYSTEM_ID,
        ))
        subsystem_setting = RadioSetting(
            'target_subsystem_id',
            'Target subsystemID (目标 subsystemID)',
            RadioSettingValueInteger(0, 255, subsystem_value),
        )
        subsystem_setting.__doc__ = (
            'Verified uint8 range 0-255. Although the command carries four '
            'bytes, the radio firmware consumes only the low byte; values '
            'above 255 would wrap modulo 256, so this driver rejects them.'
        )
        provisioning.append(subsystem_setting)

        action_value = getattr(
            self,
            '_provision_action',
            PROVISION_NONE,
        )
        action = RadioSetting(
            'provision_action',
            'Operation on Next Upload (下次上传执行)',
            RadioSettingValueMap(
                PROVISION_ACTIONS,
                mem_val=action_value,
            ),
        )
        action.set_warning(
            'This operation writes device-wide authentication or digital '             'subsystem data through a separate hidden protocol. Do not '             'disconnect power or the programming cable until it finishes.',
            safe_value=PROVISION_ACTIONS[0][0],
        )
        provisioning.append(action)

        provisioning.append(RadioSetting(
            'provision_confirm',
            'Confirm One-Shot Provisioning (确认执行一次)',
            RadioSettingValueBoolean(
                getattr(self, '_provision_confirmed', False)
            ),
        ))

        return RadioSettings(basic, audio, vox, power, provisioning)

    def set_settings(self, settings):
        """Apply verified CPS basic settings while preserving unknown bytes."""
        general, system = self._settings_blocks()

        for setting in settings.walk():
            name = setting.get_name()

            if name == 'squelch':
                system[SS_SQUELCH] = int(setting.value)
            elif name == 'side_key':
                system[SS_SIDE_KEY] = int(setting.value)
            elif name == 'timeout':
                system[SS_TIMEOUT] = int(setting.value)
            elif name == 'alarm_switch':
                general[GS_ALARM_SWITCH] = int(bool(setting.value))
            elif name == 'noise_reduction':
                general[GS_NOISE_REDUCTION] = int(bool(setting.value))
            elif name == 'language':
                general[GS_LANGUAGE] = int(setting.value)
            elif name == 'voice_switch':
                general[GS_VOICE_SWITCH] = int(bool(setting.value))
            elif name == 'beep':
                system[SS_FLAGS] = _set_flag(
                    system[SS_FLAGS],
                    SS_BEEP,
                    bool(setting.value),
                )
            elif name == 'vox_enabled':
                general[GS_VOX_STATE] = int(bool(setting.value))
            elif name == 'vox_gain':
                general[GS_VOX_GAIN] = int(setting.value)
            elif name == 'power_save':
                system[SS_FLAGS] = _set_flag(
                    system[SS_FLAGS],
                    SS_POWER_SAVE,
                    bool(setting.value),
                )
            elif name == 'low_voltage_inhibit':
                general[GS_LOW_VOLTAGE_INHIBIT] = int(
                    bool(setting.value)
                )
            elif name == 'high_voltage_inhibit':
                general[GS_HIGH_VOLTAGE_INHIBIT] = int(
                    bool(setting.value)
                )
            elif name == 'password_source':
                self._provision_password_source = (
                    setting.value.get_mem_val()
                )
            elif name == 'custom_password':
                # This value is editable and semantically "custom" only when
                # the selected source is Custom. In all other modes it is a
                # read-only display of the effective preset/current password.
                if getattr(
                    self,
                    '_provision_password_source',
                    PASSWORD_SOURCE_KEEP,
                ) == PASSWORD_SOURCE_CUSTOM:
                    password_text = str(setting.value)
                    _password_blob(password_text)
                    self._provision_custom_password = password_text
            elif name == 'target_subsystem_id':
                subsystem_id = _parse_subsystem_id(setting.value)
                self._provision_subsystem_id = subsystem_id
            elif name == 'provision_action':
                self._provision_action = setting.value.get_mem_val()
            elif name == 'provision_confirm':
                self._provision_confirmed = bool(setting.value)

        self._mmap.set(GENERAL_SETTINGS_OFFSET, bytes(general))
        self._mmap.set(SYSTEM_SETTINGS_OFFSET, bytes(system))

    def set_memory(self, memory):
        """Update one channel in the guarded clone image."""
        offset, existing = self._channel_raw(memory.number)
        existing_is_empty = existing[:4] in (
            b"\x00" * 4,
            b"\xFF" * 4,
        )

        if existing_is_empty:
            # Start with erased bytes for frequency/tone/reserved fields, then
            # initialize the CPS-visible options instead of inheriting FF bits:
            #   intercom mode = analog
            #   encryption key = 0
            #   hopping = off
            #   busy channel lockout = off
            #   transmit power = high
            raw = bytearray(b"\xFF" * CHANNEL_SIZE)
            # BCL is inverted in storage, so bit 0 must be set for "off".
            # High power is represented by byte 12 bit 3 = 1.
            raw[12] = FLAG_BCL_DISABLED | FLAG_HIGH_POWER
            raw[13] = 0x00
        else:
            raw = bytearray(existing)

        if memory.empty or not memory.freq:
            # CHIRP-next represents a cleared Frequency cell as freq == 0
            # without setting memory.empty first. The radio/CPS empty-channel
            # representation is the complete 16-byte record filled with FF.
            self._mmap.set(offset, b"\xFF" * CHANNEL_SIZE)
            return

        # Match the original CPS: invalid typed frequencies are replaced
        # with the nearest value on the 2.5/5/6.25-kHz union of grids.
        rx_freq = _nearest_supported_frequency(memory.freq)
        raw[0:4] = _encode_frequency(rx_freq)

        if memory.duplex == "off":
            raw[4:8] = b"\xFF" * 4
        elif memory.duplex == "split":
            tx_freq = _nearest_supported_frequency(memory.offset)
            raw[4:8] = _encode_frequency(tx_freq)
        elif memory.duplex == "+":
            tx_freq = _nearest_supported_frequency(
                memory.freq + memory.offset
            )
            raw[4:8] = _encode_frequency(tx_freq)
        elif memory.duplex == "-":
            tx_freq = _nearest_supported_frequency(
                memory.freq - memory.offset
            )
            raw[4:8] = _encode_frequency(tx_freq)
        else:
            raw[4:8] = _encode_frequency(rx_freq)

        tx_tone, rx_tone = _tones_from_memory(memory)
        raw[8:10] = _encode_tone(*rx_tone)
        raw[10:12] = _encode_tone(*tx_tone)

        flags = raw[12]
        flags = ((flags | FLAG_SCAN_EXCLUDED) if memory.skip == "S" else (flags & ~FLAG_SCAN_EXCLUDED))
        flags = (
            (flags | FLAG_HIGH_POWER)
            if str(memory.power) == str(POWER_LEVELS[1])
            else (flags & ~FLAG_HIGH_POWER)
        )
        flags = ((flags | FLAG_NARROW) if memory.mode == "NFM" else (flags & ~FLAG_NARROW))

        for setting in memory.extra:
            name = setting.get_name()
            if name == "intercom_mode":
                flags = (
                    (flags | FLAG_ENCRYPTED_INTERCOM)
                    if int(setting.value) == 1
                    else (flags & ~FLAG_ENCRYPTED_INTERCOM)
                )
            elif name == "bcl":
                flags = (
                    (flags & ~FLAG_BCL_DISABLED)
                    if bool(setting.value)
                    else (flags | FLAG_BCL_DISABLED)
                )
            elif name == "hopping":
                flags = (
                    (flags | FLAG_HOPPING)
                    if bool(setting.value)
                    else (flags & ~FLAG_HOPPING)
                )
            elif name == "encryption_key":
                raw[13] = (
                    (raw[13] & ~ENCRYPTION_KEY_MASK)
                    | (int(str(setting.value)) & ENCRYPTION_KEY_MASK)
                )

        raw[12] = flags
        # MemoryMapBytes requires its explicit set(address, data) API.
        self._mmap.set(offset, bytes(raw))

@directory.register
class Baofeng888SDPOFUNGRadio(Baofeng888SDRadio):
    VARIANT = "POFUNG / 外贸体验版 / provisioning v0.18"
    DEALER_CODE = "POFUNG"
    DEFAULT_SUBSYSTEM_ID = 0

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN59501Radio(Baofeng888SDRadio):
    VARIANT = "CN59501 / 王青红 / provisioning v0.18"
    DEALER_CODE = "CN59501"
    DEFAULT_SUBSYSTEM_ID = 2

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN59502Radio(Baofeng888SDRadio):
    VARIANT = "CN59502 / 王鑫源 / provisioning v0.18"
    DEALER_CODE = "CN59502"
    DEFAULT_SUBSYSTEM_ID = 3

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN59503Radio(Baofeng888SDRadio):
    VARIANT = "CN59503 / 李木旺 / provisioning v0.18"
    DEALER_CODE = "CN59503"
    DEFAULT_SUBSYSTEM_ID = 4

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN59504Radio(Baofeng888SDRadio):
    VARIANT = "CN59504 / 王景松 / provisioning v0.18"
    DEALER_CODE = "CN59504"
    DEFAULT_SUBSYSTEM_ID = 5

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN02801Radio(Baofeng888SDRadio):
    VARIANT = "CN02801 / 邓小松 / provisioning v0.18"
    DEALER_CODE = "CN02801"
    DEFAULT_SUBSYSTEM_ID = 6

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN02501Radio(Baofeng888SDRadio):
    VARIANT = "CN02501 / 姜克明 / provisioning v0.18"
    DEALER_CODE = "CN02501"
    DEFAULT_SUBSYSTEM_ID = 7

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN53601Radio(Baofeng888SDRadio):
    VARIANT = "CN53601 / 张丽丽 / provisioning v0.18"
    DEALER_CODE = "CN53601"
    DEFAULT_SUBSYSTEM_ID = 8

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN93101Radio(Baofeng888SDRadio):
    VARIANT = "CN93101 / 陈军 / provisioning v0.18"
    DEALER_CODE = "CN93101"
    DEFAULT_SUBSYSTEM_ID = 9

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN53201Radio(Baofeng888SDRadio):
    VARIANT = "CN53201 / 吴端乐 / Suofei / provisioning v0.18"
    DEALER_CODE = "CN53201"
    DEFAULT_SUBSYSTEM_ID = 10

    @classmethod
    def match_model(cls, filedata, filename):
        return False


@directory.register
class Baofeng888SDCN53901Radio(Baofeng888SDRadio):
    VARIANT = "CN53901 / LZF / provisioning v0.18"
    DEALER_CODE = "CN53901"
    DEFAULT_SUBSYSTEM_ID = 11

    @classmethod
    def match_model(cls, filedata, filename):
        return False
