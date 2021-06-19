from abc import ABCMeta, abstractmethod
import json
from datetime import datetime

from simulator.dpdp_competition.algorithm.conf.configs import configs
import simulator.dpdp_competition.algorithm.vrppd.getConfig
gConfig = simulator.dpdp_competition.algorithm.vrppd.getConfig.get_config()


class travelCost(metaclass=ABCMeta):

    @abstractmethod
    def getTravelCost(self, startPoint: str, endPoint: str, inquireTime: object = datetime.now()) -> dict:
        pass


class costDatabase(travelCost):
    def __init__(self):
        with open(configs.route_cost_map_path) as f:
            self._route_cost_map = json.load(f)

    def getTravelCost(self, startPoint, endPoint, inquireTime=datetime.now()):
        try:
            if startPoint == endPoint:
                return {"distance": 0,
                        "travel_time": 0,
                        "normal_distance": 0,
                        "normal_travelTime": 0}
            else:
                return self._route_cost_map[startPoint+endPoint]
        except:
            print(startPoint)
            print(endPoint)

