'''Tests for WMS calls'''

import unittest
from uuid import UUID
import requests_mock
from geoengine.datasets import DatasetId, UploadId, StoredDataset
import geoengine as ge


class WorkflowStorageTests(unittest.TestCase):
    '''Test methods for storing workflows as datasets'''

    def setUp(self) -> None:
        ge.reset(False)

    def test_storing_workflow(self):

        expected_request_text = ({
            'name': 'Foo',
            'description': 'Bar',
            'query': {
                           'spatialBounds': {
                               'upperLeftCoordinate': {
                                   'x': -180.0,
                                   'y': 90.0
                               },
                               'lowerRightCoordinate': {
                                   'x': 180.0,
                                   'y': -90.0
                               }
                           },
                'timeInterval': {
                               'start': 1396353600000,
                           },
                'spatialResolution': {
                               'x': 1.8,
                               'y': 1.8
                           }
            }
        })

        with requests_mock.Mocker() as m:
            m.post('http://mock-instance/anonymous', json={
                "id": "c4983c3e-9b53-47ae-bda9-382223bd5081",
                "project": None,
                "view": None
            })

            m.post('http://mock-instance/workflow',
                   json={
                       "id": "5b9508a8-bd34-5a1c-acd6-75bb832d2d38"
                   },
                   request_headers={'Authorization': 'Bearer c4983c3e-9b53-47ae-bda9-382223bd5081'})

            m.get('http://mock-instance/workflow/5b9508a8-bd34-5a1c-acd6-75bb832d2d38/metadata',
                  json={
                      "type": "raster",
                      "dataType": "U8",
                      "spatialReference": "EPSG:4326",
                      "measurement": {
                          "type": "unitless"
                      }
                  },
                  request_headers={'Authorization': 'Bearer c4983c3e-9b53-47ae-bda9-382223bd5081'})

            m.post('http://mock-instance/datasetFromWorkflow/5b9508a8-bd34-5a1c-acd6-75bb832d2d38',
                   additional_matcher=lambda request: request.json() == expected_request_text,
                   json={'task_id': '9ec828ef-c3da-4016-8cc7-79e5556267fc'},
                   request_headers={'Authorization': 'Bearer c4983c3e-9b53-47ae-bda9-382223bd5081'})

            m.get('http://mock-instance/tasks/9ec828ef-c3da-4016-8cc7-79e5556267fc/status',
                  json={'status': 'completed',
                        'info': {'dataset': '94230f0b-4e8a-4cba-9adc-3ace837fe5d4',
                                 'upload': '3086f494-d5a4-4b51-a14b-3b29f8bf7bb0'},
                        'timeTotal': '00:00:00'}, )

            ge.initialize("http://mock-instance")

            workflow_definition = {
                "type": "Raster",
                "operator": {
                    "type": "GdalSource",
                    "params": {
                        "data": {
                            "type": "internal",
                            "datasetId": "36574dc3-560a-4b09-9d22-d5945f2b8093"
                        }
                    }
                }
            }

            query = ge.api.RasterQueryRectangle({
                "spatialBounds": ge.api.SpatialPartition2D({
                    "upperLeftCoordinate": {
                        "x": -180.0,
                        "y": 90.0},
                    "lowerRightCoordinate": {
                        "x": 180.0,
                        "y": -90.0
                    }
                }),
                "timeInterval": ge.api.TimeInterval({
                    "start": 1396353600000,
                }),
                "spatialResolution": ge.api.SpatialResolution({
                    "x": 1.8,
                    "y": 1.8
                })
            })

            workflow = ge.register_workflow(workflow_definition)
            task = workflow.save_as_dataset(
                query,
                "Foo",
                "Bar",
            )
            task_status = task.get_status()
            stored_dataset = StoredDataset.from_response(task_status.info)

            self.assertEqual(stored_dataset.dataset_id, DatasetId(UUID("94230f0b-4e8a-4cba-9adc-3ace837fe5d4")))
            self.assertEqual(stored_dataset.upload_id, UploadId(UUID("3086f494-d5a4-4b51-a14b-3b29f8bf7bb0")))
