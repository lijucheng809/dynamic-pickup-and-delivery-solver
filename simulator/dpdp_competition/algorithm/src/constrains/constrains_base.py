from abc import ABCMeta, abstractmethod


class ConstrainsBase(metaclass=ABCMeta):

    @abstractmethod
    def isFeasible(self) -> bool:
        pass

