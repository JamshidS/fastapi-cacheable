"""
Supports multiple serialization formats with automatic type detection and handling
of common FastAPI data types including Pydantic models, dataclasses, datetime objects,
and more.
"""

import json
import pickle
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional, Union
from uuid import UUID
import warnings

try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False

try:
    from pydantic import BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


class SerializationFormat(str, Enum):
    """Supported serialization formats."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"


class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles additional Python types commonly used in FastAPI.
    
    Supports:
    - datetime, date, time objects
    - UUID
    - Decimal
    - Pydantic models
    - dataclasses
    - Enums
    - bytes
    - sets
    - timedelta
    """
    
    def default(self, obj: Any) -> Any:
        # Handle datetime objects
        if isinstance(obj, datetime):
            return {"__type__": "datetime", "value": obj.isoformat()}
        
        if isinstance(obj, date):
            return {"__type__": "date", "value": obj.isoformat()}
        
        if isinstance(obj, time):
            return {"__type__": "time", "value": obj.isoformat()}
        
        if isinstance(obj, timedelta):
            return {"__type__": "timedelta", "value": obj.total_seconds()}
        
        if isinstance(obj, UUID):
            return {"__type__": "uuid", "value": str(obj)}
        
        if isinstance(obj, Decimal):
            return {"__type__": "decimal", "value": str(obj)}
        
        if isinstance(obj, Enum):
            return {"__type__": "enum", "module": obj.__class__.__module__, 
                    "name": obj.__class__.__name__, "value": obj.value}

        if isinstance(obj, bytes):
            return {"__type__": "bytes", "value": obj.decode("latin-1")}
        
        if isinstance(obj, set):
            return {"__type__": "set", "value": list(obj)}
        
        if isinstance(obj, frozenset):
            return {"__type__": "frozenset", "value": list(obj)}
        
        if PYDANTIC_AVAILABLE and isinstance(obj, BaseModel):
            return {
                "__type__": "pydantic",
                "model": f"{obj.__class__.__module__}.{obj.__class__.__name__}",
                "value": obj.model_dump()
            }
        
        # Handle dataclasses
        if hasattr(obj, "__dataclass_fields__"):
            from dataclasses import asdict
            return {
                "__type__": "dataclass",
                "class": f"{obj.__class__.__module__}.{obj.__class__.__name__}",
                "value": asdict(obj)
            }
        
        return super().default(obj)


def _json_object_hook(obj: dict) -> Any:
    """
    Custom JSON decoder hook for deserializing custom types.
    
    :param obj: Dictionary to decode
    :return: Decoded Python object
    """
    if "__type__" not in obj:
        return obj
    
    obj_type = obj["__type__"]
    
    if obj_type == "datetime":
        return datetime.fromisoformat(obj["value"])
    
    if obj_type == "date":
        return date.fromisoformat(obj["value"])
    
    if obj_type == "time":
        return time.fromisoformat(obj["value"])
    
    if obj_type == "timedelta":
        return timedelta(seconds=obj["value"])

    if obj_type == "uuid":
        return UUID(obj["value"])
    
    if obj_type == "decimal":
        return Decimal(obj["value"])
    
    if obj_type == "enum":
        # Dynamically import the enum class
        module_path = obj["module"]
        class_name = obj["name"]
        try:
            module = __import__(module_path, fromlist=[class_name])
            enum_class = getattr(module, class_name)
            return enum_class(obj["value"])
        except (ImportError, AttributeError):
            # If we can't import the enum, return the value
            return obj["value"]
    
    if obj_type == "bytes":
        return obj["value"].encode("latin-1")
    
    if obj_type == "set":
        return set(obj["value"])
    
    if obj_type == "frozenset":
        return frozenset(obj["value"])

    if obj_type == "pydantic" and PYDANTIC_AVAILABLE:
        model_path = obj["model"]
        module_path, class_name = model_path.rsplit(".", 1)
        try:
            module = __import__(module_path, fromlist=[class_name])
            model_class = getattr(module, class_name)
            return model_class(**obj["value"])
        except (ImportError, AttributeError):
            # If we can't import the model, return the dict
            return obj["value"]
    
    if obj_type == "dataclass":
        class_path = obj["class"]
        module_path, class_name = class_path.rsplit(".", 1)
        try:
            module = __import__(module_path, fromlist=[class_name])
            dataclass_type = getattr(module, class_name)
            return dataclass_type(**obj["value"])
        except (ImportError, AttributeError):
            # If we can't import the dataclass, return the dict
            return obj["value"]
    
    return obj


def serialize_json(data: Any) -> bytes:
    """
    Serialize data to JSON format with support for custom types.
    
    :param data: Data to serialize
    :return: Serialized bytes
    """
    json_str = json.dumps(data, cls=JSONEncoder, separators=(',', ':'), ensure_ascii=False)
    return json_str.encode('utf-8')


def deserialize_json(data: bytes) -> Any:
    """
    Deserialize JSON data with support for custom types.
    
    :param data: Serialized bytes
    :return: Deserialized Python object
    """
    json_str = data.decode('utf-8')
    return json.loads(json_str, object_hook=_json_object_hook)


def serialize_pickle(data: Any) -> bytes:
    """
    Serialize data using pickle protocol 4 (Python 3.4+).
    
    Note: Pickle is the most flexible but least secure. Only use with trusted data.
    
    :param data: Data to serialize
    :return: Serialized bytes
    """
    warnings.warn(
        "Pickle serialization is unsafe for untrusted data. "
        "Only use with trusted cache backends.",
        RuntimeWarning,
        stacklevel=2,
    )
    return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)


def deserialize_pickle(data: bytes) -> Any:
    """
    Deserialize pickle data.
    
    :param data: Serialized bytes
    :return: Deserialized Python object
    """
    return pickle.loads(data)


def serialize_msgpack(data: Any) -> bytes:
    """
    Serialize data using MessagePack format.
    
    Requires msgpack package to be installed.
    Falls back to JSON if msgpack is not available.
    Note: Msgpack uses JSON-compatible transformation internally
    
    :param data: Data to serialize
    :return: Serialized bytes
    """
    if not MSGPACK_AVAILABLE:
        return serialize_json(data)
    
    # Convert to JSON-serializable format first using our custom encoder
    json_compatible = json.loads(json.dumps(data, cls=JSONEncoder))
    return msgpack.packb(json_compatible, use_bin_type=True)


def deserialize_msgpack(data: bytes) -> Any:
    """
    Deserialize MessagePack data.
    
    Requires msgpack package to be installed.
    Falls back to JSON if msgpack is not available.
    
    :param data: Serialized bytes
    :return: Deserialized Python object
    """
    if not MSGPACK_AVAILABLE:
        return deserialize_json(data)
    
    unpacked = msgpack.unpackb(data, raw=False)
    # Apply the same object hook as JSON to restore custom types
    return json.loads(json.dumps(unpacked), object_hook=_json_object_hook)


# Default serialization format
_DEFAULT_FORMAT = SerializationFormat.JSON

# Serializer registry
_SERIALIZERS: dict[SerializationFormat, Callable[[Any], bytes]] = {
    SerializationFormat.JSON: serialize_json,
    SerializationFormat.PICKLE: serialize_pickle,
    SerializationFormat.MSGPACK: serialize_msgpack,
}

# Deserializer registry
_DESERIALIZERS: dict[SerializationFormat, Callable[[bytes], Any]] = {
    SerializationFormat.JSON: deserialize_json,
    SerializationFormat.PICKLE: deserialize_pickle,
    SerializationFormat.MSGPACK: deserialize_msgpack,
}


def set_default_format(format: SerializationFormat) -> None:
    """
    Set the default serialization format.
    
    :param format: Serialization format to use
    """
    global _DEFAULT_FORMAT
    _DEFAULT_FORMAT = format


def get_default_format() -> SerializationFormat:
    """
    Get the current default serialization format.
    
    :return: Current default format
    """
    return _DEFAULT_FORMAT


def register_serializer(
    format: Union[str, SerializationFormat],
    serializer: Callable[[Any], bytes],
    deserializer: Callable[[bytes], Any]
) -> None:
    """
    Register a custom serializer/deserializer pair.
    
    :param format: Format identifier
    :param serializer: Serialization function
    :param deserializer: Deserialization function
    """
    if isinstance(format, str):
        format = SerializationFormat(format)
    
    _SERIALIZERS[format] = serializer
    _DESERIALIZERS[format] = deserializer


def serialize(
    data: Any,
    format: Optional[SerializationFormat] = None
) -> bytes:
    """
    Serialize data to bytes using the specified or default format.
    
    :param data: Data to serialize
    :param format: Optional serialization format (uses default if not specified)
    :return: Serialized bytes
    :raises ValueError: If the format is not supported
    """
    if format is None:
        format = _DEFAULT_FORMAT
    
    if format not in _SERIALIZERS:
        raise ValueError(f"Unsupported serialization format: {format}")
    
    try:
        serializer = _SERIALIZERS[format]
        return serializer(data)
    except Exception as e:
        raise ValueError(f"Failed to serialize data with format {format}: {str(e)}") from e


def deserialize(
    data: bytes,
    format: Optional[SerializationFormat] = None
) -> Any:
    """
    Deserialize bytes to Python object using the specified or default format.
    
    :param data: Serialized bytes
    :param format: Optional serialization format (uses default if not specified)
    :return: Deserialized Python object
    :raises ValueError: If the format is not supported or deserialization fails
    """
    if format is None:
        format = _DEFAULT_FORMAT
    
    if format not in _DESERIALIZERS:
        raise ValueError(f"Unsupported deserialization format: {format}")
    
    try:
        deserializer = _DESERIALIZERS[format]
        return deserializer(data)
    except Exception as e:
        raise ValueError(f"Failed to deserialize data with format {format}: {str(e)}") from e


__all__ = [
    "serialize",
    "deserialize",
    "SerializationFormat",
    "set_default_format",
    "get_default_format",
    "register_serializer",
    "JSONEncoder",
    "serialize_json",
    "deserialize_json",
    "serialize_pickle",
    "deserialize_pickle",
    "serialize_msgpack",
    "deserialize_msgpack",
]
