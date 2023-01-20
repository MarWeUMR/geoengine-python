'''
Different type mappings of geo engine types
'''

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
from uuid import UUID

from enum import Enum
from attr import dataclass
from geoengine.colorizer import Colorizer
from geoengine import api
from geoengine.error import GeoEngineException, InputException, TypeException


class QueryRectangle:
    '''
    A multi-dimensional query rectangle, consisting of spatial and temporal information.
    '''

    __spatial_bounds: Tuple[float, float, float, float]
    __time_interval: Tuple[datetime, datetime]
    __resolution: Tuple[float, float]
    __srs: str

    def __init__(self,
                 spatial_bounds: Tuple[float, float, float, float],
                 time_interval: Tuple[datetime, datetime],
                 resolution: Tuple[float, float] = (0.1, 0.1),
                 srs='EPSG:4326') -> None:
        '''Initialize a new `QueryRectangle` object'''
        xmin = spatial_bounds[0]
        ymin = spatial_bounds[1]
        xmax = spatial_bounds[2]
        ymax = spatial_bounds[3]

        if (xmin > xmax) or (ymin > ymax):
            raise InputException("Bbox: Malformed since min must be <= max")

        self.__spatial_bounds = spatial_bounds

        if time_interval[0] > time_interval[1]:
            raise InputException("Time inverval: Start must be <= End")

        self.__time_interval = time_interval

        if resolution[0] <= 0 or resolution[1] <= 0:
            raise InputException("Resolution: Must be positive")

        self.__resolution = resolution

        self.__srs = srs

    @property
    def bbox_str(self) -> str:
        '''
        A comma-separated string representation of the spatial bounds
        '''

        return ','.join(map(str, self.__spatial_bounds))

    @property
    def bbox_ogc_str(self) -> str:
        '''
        A comma-separated string representation of the spatial bounds with OGC axis ordering
        '''

        return ','.join(map(str, self.bbox_ogc))

    @property
    def bbox_ogc(self) -> Tuple[float, float, float, float]:
        '''
        Return the bbox with OGC axis ordering of the srs
        '''

        # TODO: properly handle axis order
        bbox = self.__spatial_bounds

        if self.__srs == "EPSG:4326":
            return (bbox[1], bbox[0], bbox[3], bbox[2])

        return bbox

    @property
    def resolution_ogc(self) -> Tuple[float, float]:
        '''
        Return the resolution in OGC style
        '''

        # TODO: properly handle axis order
        res = self.__resolution

        if self.__srs == "EPSG:4326":
            return (-res[1], res[0])

        return res

    @property
    def xmin(self) -> float:
        return self.__spatial_bounds[0]

    @property
    def ymin(self) -> float:
        return self.__spatial_bounds[1]

    @property
    def xmax(self) -> float:
        return self.__spatial_bounds[2]

    @property
    def ymax(self) -> float:
        return self.__spatial_bounds[3]

    @property
    def time_str(self) -> str:
        '''
        Return the time instance or interval as a string representation
        '''

        if self.__time_interval[0] == self.__time_interval[1]:
            return self.__time_interval[0].isoformat(timespec='milliseconds')

        return '/'.join(map(str, self.__time_interval))

    @property
    def resolution(self) -> Tuple[float, float]:
        '''
        Return the resolution as is
        '''

        return self.__resolution

    @property
    def srs(self) -> str:
        '''
        Return the SRS string
        '''

        return self.__srs

    def __dict__(self):
        '''
        Return a dictionary representation of the object
        '''

        time_start_unix = int(self.__time_interval[0].timestamp() * 1000)
        time_end_unix = int(self.__time_interval[1].timestamp() * 1000)

        left_x = min(self.__spatial_bounds[0], self.__spatial_bounds[2])
        right_x = max(self.__spatial_bounds[0], self.__spatial_bounds[2])
        lower_y = min(self.__spatial_bounds[1], self.__spatial_bounds[3])
        upper_y = max(self.__spatial_bounds[1], self.__spatial_bounds[3])

        # TODO: distinguish between raster, vector and plot query rectangle

        return {
            'spatialBounds': {
                'upperLeftCoordinate': {
                    "x": left_x,
                    "y": upper_y,
                },
                'lowerRightCoordinate': {
                    "x": right_x,
                    "y": lower_y,
                }
            },
            'timeInterval': {
                'start': time_start_unix,
                'end': time_end_unix,
            },
            'spatialResolution': {
                'x': self.__resolution[0],
                'y': self.__resolution[1],
            },
        }


class ResultDescriptor:  # pylint: disable=too-few-public-methods
    '''
    Base class for result descriptors
    '''

    __spatial_reference: str

    def __init__(self, spatial_reference: str) -> None:
        self.__spatial_reference = spatial_reference

    @staticmethod
    def from_response(response: api.ResultDescriptor) -> ResultDescriptor:
        '''
        Parse a result descriptor from an http response
        '''

        if 'error' in response:
            raise GeoEngineException(response)

        result_descriptor_type = response['type']

        if result_descriptor_type == 'raster':
            return RasterResultDescriptor.from_response(response)
        if result_descriptor_type == 'vector':
            return VectorResultDescriptor.from_response(response)
        if result_descriptor_type == 'plot':
            return PlotResultDescriptor.from_response(response)

        raise TypeException(
            f'Unknown `ResultDescriptor` type: {result_descriptor_type}')

    @classmethod
    def is_raster_result(cls) -> bool:
        '''
        Return true if the result is of type raster
        '''

        return False

    @classmethod
    def is_vector_result(cls) -> bool:
        '''
        Return true if the result is of type vector
        '''

        return False

    @classmethod
    def is_plot_result(cls) -> bool:
        '''
        Return true if the result is of type plot
        '''

        return False

    @property
    def spatial_reference(self) -> str:
        '''Return the spatial reference'''

        return self.__spatial_reference

    @abstractmethod
    def to_api_dict(self) -> api.ResultDescriptor:
        pass

    def __iter__(self):
        return iter(self.to_api_dict().items())


class VectorResultDescriptor(ResultDescriptor):
    '''
    A vector result descriptor
    '''

    __data_type: str
    __columns: Dict[str, VectorColumnInfo]

    def __init__(self, spatial_reference: str, data_type: str, columns: Dict[str, VectorColumnInfo]) -> None:
        ''' Initialize a vector result descriptor '''
        super().__init__(spatial_reference)
        self.__data_type = data_type
        self.__columns = columns

    def __repr__(self) -> str:
        '''Display representation of the vector result descriptor'''
        r = ''
        r += f'Data type:         {self.data_type}\n'
        r += f'Spatial Reference: {self.spatial_reference}\n'

        r += 'Columns:\n'
        for column_name in self.columns:
            column_info = self.columns[column_name]
            r += f'  {column_name}:\n'
            r += f'    Column Type: {column_info.data_type}\n'
            r += f'    Measurement: {column_info.measurement}\n'

        return r

    @staticmethod
    def from_response(response: api.VectorResultDescriptor) -> VectorResultDescriptor:
        '''Parse a vector result descriptor from an http response'''
        sref = response['spatialReference']
        data_type = response['dataType']
        columns = {name: VectorColumnInfo.from_response(info) for name, info in response['columns'].items()}
        return VectorResultDescriptor(sref, data_type, columns)

    @ classmethod
    def is_vector_result(cls) -> bool:
        return True

    @ property
    def data_type(self) -> str:
        '''Return the data type'''

        return self.__data_type

    @ property
    def spatial_reference(self) -> str:
        '''Return the spatial reference'''

        return super().spatial_reference

    @ property
    def columns(self) -> Dict[str, VectorColumnInfo]:
        '''Return the columns'''

        return self.__columns

    def to_api_dict(self) -> api.VectorResultDescriptor:
        '''Convert the vector result descriptor to a dictionary'''

        return api.VectorResultDescriptor({
            'type': 'raster',
            'dataType': self.data_type,
            'spatialReference': self.spatial_reference,
            'columns': api.VectorColumnInfo(
                {name: column_info.to_api_dict() for name, column_info in self.columns.items()}
            ),
        })


@ dataclass
class VectorColumnInfo:
    '''Vector column information'''

    data_type: str
    measurement: Measurement

    @ staticmethod
    def from_response(response: api.VectorColumnInfo) -> VectorColumnInfo:
        '''Create a new `VectorColumnInfo` from a JSON response'''

        return VectorColumnInfo(response['dataType'], Measurement.from_response(response['measurement']))

    def to_api_dict(self) -> api.VectorColumnInfo:
        '''Convert to a dictionary'''

        return api.VectorColumnInfo({
            'dataType': self.data_type,
            'measurement': self.measurement.to_api_dict(),
        })


class RasterResultDescriptor(ResultDescriptor):
    '''
    A raster result descriptor
    '''

    __data_type: str
    __measurement: Measurement

    def __init__(self, data_type: str, measurement: Measurement, spatial_reference: str) -> None:
        '''Initialize a new `RasterResultDescriptor`'''
        super().__init__(spatial_reference)
        self.__data_type = data_type
        self.__measurement = measurement

    def __repr__(self) -> str:
        '''Display representation of the raster result descriptor'''
        r = ''
        r += f'Data type:         {self.data_type}\n'
        r += f'Spatial Reference: {self.spatial_reference}\n'
        r += f'Measurement:       {self.measurement}\n'

        return r

    def to_api_dict(self) -> api.RasterResultDescriptor:
        '''Convert the raster result descriptor to a dictionary'''

        return {
            'type': 'raster',
            'dataType': self.data_type,
            'measurement': self.measurement.to_api_dict(),
            'spatialReference': self.spatial_reference,
        }

    @ staticmethod
    def from_response(response: api.RasterResultDescriptor) -> RasterResultDescriptor:
        spatial_ref = response['spatialReference']
        data_type = response['dataType']
        measurement = Measurement.from_response(response['measurement'])
        return RasterResultDescriptor(data_type=data_type, measurement=measurement, spatial_reference=spatial_ref)

    @ classmethod
    def is_raster_result(cls) -> bool:
        return True

    @ property
    def data_type(self) -> str:
        return self.__data_type

    @ property
    def measurement(self) -> Measurement:
        return self.__measurement

    @ property
    def spatial_reference(self) -> str:
        '''Return the spatial reference'''

        return super().spatial_reference

    def to_json(self) -> dict:
        return self.to_api_dict()


class PlotResultDescriptor(ResultDescriptor):
    '''
    A plot result descriptor
    '''

    def __repr__(self) -> str:
        '''Display representation of the plot result descriptor'''
        r = 'Plot Result'

        return r

    @ staticmethod
    def from_response(response: api.PlotResultDescriptor) -> PlotResultDescriptor:
        '''Create a new `PlotResultDescriptor` from a JSON response'''
        spatial_ref = response['spatialReference']
        return PlotResultDescriptor(spatial_reference=spatial_ref)

    @ classmethod
    def is_plot_result(cls) -> bool:
        return True

    @ property
    def spatial_reference(self) -> str:
        '''Return the spatial reference'''

        return super().spatial_reference

    def to_api_dict(self) -> api.PlotResultDescriptor:
        '''Convert the plot result descriptor to a dictionary'''

        return api.PlotResultDescriptor({
            'type': 'plot',
            'spatialReference': self.spatial_reference,
        })


class VectorDataType(Enum):
    '''An enum of vector data types'''

    DATA = 'Data'
    MULTI_POINT = 'MultiPoint'
    MULTI_LINE_STRING = 'MultiLineString'
    MULTI_POLYGON = 'MultiPolygon'

    @ classmethod
    def from_geopandas_type_name(cls, name: str) -> VectorDataType:
        '''Resolve vector data type from geopandas geometry type'''

        name_map = {
            "Point": VectorDataType.MULTI_POINT,
            "MultiPoint": VectorDataType.MULTI_POINT,
            "Line": VectorDataType.MULTI_LINE_STRING,
            "MultiLine": VectorDataType.MULTI_LINE_STRING,
            "Polygon": VectorDataType.MULTI_POLYGON,
            "MultiPolygon": VectorDataType.MULTI_POLYGON,
        }

        if name in name_map:
            return name_map[name]

        raise InputException("Invalid vector data type")


class TimeStepGranularity(Enum):
    '''An enum of time step granularities'''
    MILLIS = 'Millis'
    SECONDS = 'Seconds'
    MINUTES = 'Minutes'
    HOURS = 'Hours'
    DAYS = 'Days'
    MONTHS = 'Months'
    YEARS = 'Years'


@ dataclass
class TimeStep:
    '''A time step that consists of a granularity and a step size'''
    step: int
    granularity: TimeStepGranularity

    def to_api_dict(self) -> api.TimeStep:
        return api.TimeStep({
            'step': self.step,
            'granularity': self.granularity.value,
        })


@ dataclass
class Provenance:
    '''Provenance information as triplet of citation, license and uri'''

    citation: str
    license: str
    uri: str

    @ classmethod
    def from_response(cls, response: api.Provenance) -> Provenance:
        '''Parse an http response to a `Provenance` object'''
        return Provenance(response['citation'], response['license'], response['uri'])

    def to_api_dict(self) -> api.Provenance:
        return api.Provenance({
            'citation': self.citation,
            'license': self.license,
            'uri': self.uri,
        })


@ dataclass
class ProvenanceOutput:
    '''Provenance of a dataset'''

    data: DataId
    provenance: Provenance

    @ classmethod
    def from_response(cls, response: api.ProvenanceOutput) -> ProvenanceOutput:
        '''Parse an http response to a `ProvenanceOutput` object'''

        dataset = DataId.from_response(response['data'])
        provenance = Provenance.from_response(response['provenance'])

        return ProvenanceOutput(dataset, provenance)


class Symbology:
    '''Base class for symbology'''

    @ abstractmethod
    def to_api_dict(self) -> api.Symbology:
        pass


class RasterSymbology(Symbology):
    '''A raster symbology'''
    __opacity: float
    __colorizer: Colorizer

    def __init__(self, colorizer: Colorizer, opacity: float = 0.0) -> None:
        '''Initialize a new `RasterSymbology`'''

        self.__colorizer = colorizer
        self.__opacity = opacity

    def to_api_dict(self) -> api.RasterSymbology:
        '''Convert the raster symbology to a dictionary'''

        return api.RasterSymbology({
            'type': 'raster',
            'colorizer': self.__colorizer.to_api_dict(),
            'opacity': self.__opacity,
        })


class DataId:  # pylint: disable=too-few-public-methods
    '''Base class for data ids'''
    @ classmethod
    def from_response(cls, response: api.DataId) -> DataId:
        '''Parse an http response to a `DataId` object'''

        if response["type"] == "internal":
            return InternalDataId.from_response(response)
        if response["type"] == "external":
            return ExternalDataId.from_response(response)

        raise GeoEngineException({"message": f"Unknown DataId type: {response['type']}"})

    @ abstractmethod
    def to_api_dict(self) -> api.DataId:
        pass


class InternalDataId(DataId):
    '''An internal data id'''

    __dataset_id: UUID

    def __init__(self, dataset_id: UUID):
        self.__dataset_id = dataset_id

    @ classmethod
    def from_response(cls, response: api.InternalDataId) -> InternalDataId:
        '''Parse an http response to a `InternalDataId` object'''

        return InternalDataId(UUID(response['datasetId']))

    def to_api_dict(self) -> api.InternalDataId:
        return api.InternalDataId({
            "type": "internal",
            "datasetId": str(self.__dataset_id)
        })

    def __str__(self) -> str:
        return str(self.__dataset_id)

    def __repr__(self) -> str:
        '''Display representation of an internal data id'''
        return str(self)

    def __eq__(self, other) -> bool:
        '''Check if two internal data ids are equal'''
        if not isinstance(other, self.__class__):
            return False

        return self.__dataset_id == other.__dataset_id  # pylint: disable=protected-access


class ExternalDataId(DataId):
    '''An external data id'''

    __provider_id: UUID
    __layer_id: str

    def __init__(self, provider_id: UUID, layer_id: str):
        self.__provider_id = provider_id
        self.__layer_id = layer_id

    @ classmethod
    def from_response(cls, response: api.ExternalDataId) -> ExternalDataId:
        '''Parse an http response to a `ExternalDataId` object'''

        return ExternalDataId(UUID(response['providerId']), response['layerId'])

    def to_api_dict(self) -> api.ExternalDataId:
        return api.ExternalDataId({
            "type": "external",
            "providerId": str(self.__provider_id),
            "layerId": self.__layer_id,
        })

    def __str__(self) -> str:
        return f'{self.__provider_id}:{self.__layer_id}'

    def __repr__(self) -> str:
        '''Display representation of an external data id'''
        return str(self)

    def __eq__(self, other) -> bool:
        '''Check if two external data ids are equal'''
        if not isinstance(other, self.__class__):
            return False

        return self.__provider_id == other.__provider_id and self.__layer_id == other.__layer_id  # pylint: disable=protected-access


class Measurement:  # pylint: disable=too-few-public-methods
    '''
    Base class for measurements
    '''

    @ staticmethod
    def from_response(response: api.Measurement) -> Measurement:
        '''
        Parse a result descriptor from an http response
        '''

        if 'error' in response:
            raise GeoEngineException(response)

        measurement_type = response['type']

        if measurement_type == 'unitless':
            return UnitlessMeasurement()
        if measurement_type == 'continuous':
            return ContiuousMeasurement.from_response(response)
        if measurement_type == 'classification':
            return ClassificationMeasurement.from_response(response)

        raise TypeException(
            f'Unknown `Measurement` type: {measurement_type}')

    @ abstractmethod
    def to_api_dict(self) -> api.Measurement:
        pass


class UnitlessMeasurement(Measurement):
    '''A measurement that is unitless'''

    def __str__(self) -> str:
        '''String representation of a unitless measurement'''
        return 'unitless'

    def __repr__(self) -> str:
        '''Display representation of a unitless measurement'''
        return str(self)

    def to_api_dict(self) -> api.UnitlessMeasurement:
        return api.UnitlessMeasurement({
            'type': 'unitless'
        })


class ContiuousMeasurement(Measurement):
    '''A measurement that is continuous'''

    __measurement: str
    __unit: Optional[str]

    def __init__(self, measurement: str, unit: Optional[str]) -> None:
        '''Initialize a new `ContiuousMeasurement`'''

        super().__init__()

        self.__measurement = measurement
        self.__unit = unit

    @ staticmethod
    def from_response(response: api.ContiuousMeasurement) -> ContiuousMeasurement:
        '''Initialize a new `ContiuousMeasurement from a JSON response'''

        return ContiuousMeasurement(response['measurement'], response.get('unit', None))

    def __str__(self) -> str:
        '''String representation of a continuous measurement'''

        if self.__unit is None:
            return self.__measurement

        return f'{self.__measurement} ({self.__unit})'

    def __repr__(self) -> str:
        '''Display representation of a continuous measurement'''
        return str(self)

    def to_api_dict(self) -> api.ContinuousMeasurement:
        return api.ContinuousMeasurement({
            'type': 'continuous',
            'measurement': self.__measurement,
            'unit': self.__unit
        })

    @ property
    def measurement(self) -> str:
        return self.__measurement

    @ property
    def unit(self) -> Optional[str]:
        return self.__unit


class ClassificationMeasurement(Measurement):
    '''A measurement that is a classification'''

    __measurement: str
    __classes: Dict[int, str]

    def __init__(self, measurement: str, classes: Dict[int, str]) -> None:
        '''Initialize a new `ClassificationMeasurement`'''

        super().__init__()

        self.__measurement = measurement
        self.__classes = classes

    @ staticmethod
    def from_response(response: api.ContinuousMeasurement) -> ClassificationMeasurement:
        '''Initialize a new `ClassificationMeasurement from a JSON response'''

        measurement = response['measurement']

        str_classes: Dict[str, str] = response['classes']
        classes = {int(k): v for k, v in str_classes.items()}

        return ClassificationMeasurement(measurement, classes)

    def to_api_dict(self) -> Dict[str, Any]:
        return api.ContinuousMeasurement({
            'type': 'classification',
            'measurement': self.__measurement,
            'classes': self.__classes
        })

    def __str__(self) -> str:
        '''String representation of a classification measurement'''
        classes_str = ', '.join(f'{k}: {v}' for k, v in self.__classes.items())
        return f'{self.__measurement} ({classes_str})'

    def __repr__(self) -> str:
        '''Display representation of a classification measurement'''
        return str(self)

    @ property
    def measurement(self) -> str:
        return self.__measurement

    @ property
    def classes(self) -> Dict[int, str]:
        return self.__classes
