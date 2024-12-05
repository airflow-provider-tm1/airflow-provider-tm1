import logging

from airflow.sensors.base_sensor_operator import BaseSensorOperator

from airflow_provider_tm1.hooks.tm1 import TM1Hook


class CellSetSensor(BaseSensorOperator):
    """
    Sensor that executes an MDX query against a TM1 server and checks if the resulting cellset is non-empty.
    This sensor uses the TM1Hook to connect to a TM1 server and execute the provided MDX query. 
    
    #? It can optionally log the estimated cellset size if the `verbose` parameter is set to True.
    
    :param tm1_conn_id: Connection ID for the TM1 server
    :type tm1_conn_id: str
    :param mdx: A valid MDX query to be executed
    :type mdx: str
    :param verbose: If True, logs the estimated cellset size of the MDX query under non-surpass zero condition
    :type verbose: bool
    :param kwargs: Additional keyword arguments passed to the BaseSensorOperator
    """
    
    def __init__(self, tm1_conn_id: str, mdx: str, verbose: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.conn_id = tm1_conn_id
        self.mdx = mdx
        self.kwargs = kwargs
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.verbose = verbose

    def poke(self, context) -> bool:
        with TM1Hook(tm1_conn_id=self.conn_id).get_conn() as tm1:
            self.logger.info("Executing MDX: %s", self.mdx)
            if self.verbose:
                self.logger.debug("Estimated MDX cell count: %s", tm1.cells.execute_mdx_cellcount(self.mdx))
            cellset = tm1.cells.execute_mdx_values(self.mdx, skip_zeros=True, **self.kwargs)
            return bool(cellset)
