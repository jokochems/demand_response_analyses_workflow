from fameio.source.cli import Config

from dr_analyses.workflow_routines import (
    get_all_yaml_files_in_folder_except,
    make_scenario_config, run_amiris, convert_amiris_results
)

input_folder = "C:/Users/koch_j0/AMIRIS/asgard/input/demand_response"

config_make = {
    Config.LOG_LEVEL: "error",
    Config.LOG_FILE: None,
    # Config.NUM_PROCESSES: 1,
}

run_properties = {
    "exe": "amiris/amiris-asgard-jar-with-dependencies.jar",
    "logging": "-Dlog4j.configuration=file:amiris/log4j.properties",
    "main": "de.dlr.gitlab.fame.setup.FameRunner",
    "setup": "amiris/fameSetup.yaml"
}

config_convert = {
    Config.LOG_LEVEL: "warn",
    Config.LOG_FILE: None,
    Config.OUTPUT: "./results/",
    Config.AGENT_LIST: None,
    Config.SINGLE_AGENT_EXPORT: False,
}

if __name__ == "__main__":
    to_ignore = ["schema.yaml"]
    scenario_files = get_all_yaml_files_in_folder_except(
        input_folder, to_ignore
    )
    for scenario in scenario_files:
        make_scenario_config(scenario, config_make, input_folder)
        run_amiris(run_properties, config_make)
        # TODO: RESUME HERE!
        convert_amiris_results()
        break
