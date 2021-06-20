import configparser
from simulator.dpdp_competition.algorithm.conf.configs import configs


def get_config(config_file=configs.config_ini_path):
    parser = configparser.ConfigParser()
    parser.read(config_file)
    _conf_ints = [(key, int(value)) for key, value in parser.items('ints')]
    _conf_floats = [(key, float(value)) for key, value in parser.items('floats')]
    _conf_strings = [(key, str(value)) for key, value in parser.items('strings')]
    return dict(_conf_ints + _conf_floats + _conf_strings)


if __name__ == '__main__':
    gConfig = get_config(config_file='config/config.ini')
    print(gConfig["static_process_time_on_customer"])