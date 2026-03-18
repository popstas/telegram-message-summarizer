import pytest
import yaml


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def config_file(tmp_data_dir):
    def _create(config_dict):
        path = tmp_data_dir / "config.yml"
        with open(path, "w") as f:
            yaml.dump(config_dict, f)
        return path

    return _create
