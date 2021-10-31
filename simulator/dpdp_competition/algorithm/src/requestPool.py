from datetime import datetime, timedelta


class RequestPool(object):
    def __init__(self):
        """
        是否需要对requests按紧急程度进行排序？
        requests: dict
          key:     requestID
          value:   {"pickup_demand_info": pickupDemandInfo
                   "delivery_demand_info": deliveryDemandInfo，
                   ”creation_time“: time,
                   "finish_time": None}
        pickupCustomer = {"customerID": ID,
                          "customerPosition": position,
                          "demand": volume,
                          "time_window": timeWindow}
        """
        self._unDispatchedRequestPool = dict()
        self._dispatchedRequestPool = dict()
        self._finishedRequestPool = dict()

    def updateUnDispatchRequest(self, requests: dict, index="add"):
        """
        :param requests:
        :param index: type: str, [add, dispatch]
        :return: None
        """
        if index == "add":
            for key, value in requests.items():
                self._unDispatchedRequestPool[key] = value
        else:
            for key in requests:
                self._unDispatchedRequestPool.pop(key)

    def updateDispatchedRequestPool(self,
                                    requestID: str,
                                    index: str,
                                    requestFinishTime=datetime.now()):
        """
        :param requestID:
        :param index: type: str, [add, finish, remove]
        :param requestFinishTime: type: datetime
        :return: None
        """
        if index == "add":
            self._dispatchedRequestPool[requestID] = self._unDispatchedRequestPool[requestID]
            self._unDispatchedRequestPool.pop(requestID)
        elif index == "finish":
            self._dispatchedRequestPool[requestID]["finishTime"] = requestFinishTime
            self._updateFinishedRequestPool(requestID)
            self._dispatchedRequestPool.pop(requestID)
        else:
            self._dispatchedRequestPool.pop(requestID)

    def _updateFinishedRequestPool(self, requestID: str):
        """
        如果request完成，则将完成的request更新至finishedRequestPool中
        :param requestID: dict
        :return: None
        """
        self._finishedRequestPool[requestID] = self._dispatchedRequestPool[requestID]

    def emptyUnDispatchedPool(self):
        if not bool(self._unDispatchedRequestPool):
            return True
        return False

    @property
    def getUnDispatchedPool(self):
        return self._unDispatchedRequestPool

    @property
    def getDispatchedPool(self):
        return self._dispatchedRequestPool
