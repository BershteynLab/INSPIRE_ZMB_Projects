import argparse
import itertools
import os
import numpy as np
import pandas as pd

from calibtool.ParameterSet import ParameterSet, NaNDetectedError

from dtk.utils.builders.TemplateHelper import TemplateHelper
from dtk.utils.core.DTKConfigBuilder import DTKConfigBuilder
from simtools.ExperimentManager.ExperimentManagerFactory import ExperimentManagerFactory
from simtools.ModBuilder import ModBuilder
from simtools.SetupParser import SetupParser
from simtools.Utilities.Initialization import load_config_module

import hiv.scripts.download as dl

from hiv.utils.utils import add_post_channel_config_as_asset

SetupParser.default_block = 'HPC'

DEFAULT_BLOCK = 'HPC'

SCENARIO_TABLE_MODE = 'scenario_table'
SCENARIO_TEMPLATE_SETS_MODE = 'scenario_template_sets'

DEFAULT_CAMPAIGN = 'Default_Campaign'


class MissingCampaignSpecificationException(Exception):
    pass


DOLPHIN = '''
                                  _
                             _.-~~.)
       _.--~~~~~---....__  .' . .,' 
     ,'. . . . . . . . . .~- ._ (
    ( .. .g. . . . . . . . . . .~-._
 .~__.-~    ~`. . . . . . . . . . . -. 
 `----..._      ~-=~~-. . . . . . . . ~-.  
           ~-._   `-._ ~=_~~--. . . . . .~.  
            | .~-.._  ~--._-.    ~-. . . . ~-.
             \ .(   ~~--.._~'       `. . . . .~-.                ,
              `._\         ~~--.._    `. . . . . ~-.    .- .   ,'/
 . _ . -~\        _ ..  _          ~~--.`_. . . . . ~-_     ,-','`  .
           ` ._           ~                ~--. . . . .~=.-'. /. `
     - . -~            -. _ . - ~ - _   - ~     ~--..__~ _,. /   \  -
             . __ ..                   ~-               ~~_. (  `
  _ _               `-       ..  - .    . - ~ ~ .    \    ~-` ` `  `.
                                               - .  `  .   \  \ `. 
'''


def load_templates(loaded_module):
    # perform any template updates for generic scenario running
    for scenario_name, scenario_templates in loaded_module.run_calib_args['scenario_template_sets'].items():
        for template in scenario_templates['config']:
            template.set_param("Enable_Demographics_Builtin", 0, allow_new_parameters=True)


# These are two methods for traversing nested python structures of lists/dicts and converting strings representing lists
# to actual lists. e.g. {'somekey': {'a': 4, 'b': '[1,2,3]'}} => {'somekey': {'a': 4, 'b': [1,2,3]}}
def check_recurse(item, indexer):
    if isinstance(item[indexer], str):
        if '[' in item[indexer]:
            item[indexer] = eval(item[indexer])
    else:
        find_and_eval(item[indexer])


def find_and_eval(item):
    if isinstance(item, list):
        for index in range(len(item)):
            check_recurse(item, index)
    elif isinstance(item, dict):
        keys = item.keys()
        for key in keys:
            check_recurse(item, key)
    else:
        pass  # do nothing


def build_and_run_simulations(samples, scenario_template_sets, scenario_param_dicts, suite_name, loaded_module):
    # Create the default config builder
    config_builder = DTKConfigBuilder()

    # This is REQUIRED by the template
    config_builder.ignore_missing = True

    # Adding the post_channel_config.json upload to Assets/ to allow post-processing of scenario sims to occur
    reference_info = loaded_module.run_calib_args['reference_info']
    add_post_channel_config_as_asset(config_builder, reference_info['channels'],
                                     reference_info['reference'], reference_info['site_info'])

    # Create a suite to hold all the experiments
    suite_id = None

    # Create the scenarios
    for template_set_name, scenario_template_set in scenario_template_sets.items():
        # available_campaigns = scenario_template_set.pop('campaign')  # we will add the selected campaign back in later
        # generate one experiment per template_set X scenario_params combination
        for scenario_params in scenario_param_dicts:
            # Determine which campaign file to use as the campaign template for this scenario
            campaign_template_name = scenario_params.pop('Campaign', None)
            resolved_scenario_template_set = loaded_module.resolve_scenario_template_set(template_set_name=template_set_name,
                                                                                         campaign_template_name=campaign_template_name)

            # name the scenario (experiment) by combining the template set name and provided Scenario name
            sn = scenario_params['Scenario']
            campaign_string = os.path.splitext(campaign_template_name)[0] if campaign_template_name else DEFAULT_CAMPAIGN
            if sn is None:
                scenario_name = '-'.join([template_set_name, campaign_string])
            else:
                scenario_name = '-'.join([template_set_name, campaign_string, sn])

            print('Scenario: %s Using template set: %s' % (scenario_name, template_set_name))

            # map the sample parameters to model parameters
            mapped_sample_params = []
            for sample in samples:
                mapped = loaded_module.map_sample_to_model_input(sample_dict=sample.param_dict,
                                                                 template_set_name=template_set_name,
                                                                 scenario_name=scenario_name,
                                                                 campaign_filename=campaign_template_name,
                                                                 random_run_number=False)

                # for tracking which parameterization & run number is which sim/result
                mapped[dl.REP_TAG] = sample.run_number
                mapped[dl.TPI_TAG] = sample.parameterization_id

                mapped_sample_params.append(mapped)

            # Combine scenario name and scenario table parameters with sample param dicts
            combined_params = []
            for sample in mapped_sample_params:
                current = {}
                current.update(sample)
                current.update(scenario_params)
                current.update({'Scenario': scenario_name, 'Config_Name': scenario_name,
                                dl.REP_TAG: current[dl.REP_TAG]})

                # including parameterization id number (TPI) and run number as tags
                if 'TAGS' not in current:
                    current['TAGS'] = {}

                parameterization_id = current.pop(dl.TPI_TAG)
                current['TAGS'].update({dl.TPI_TAG: parameterization_id,
                                        dl.REP_TAG: current[dl.REP_TAG]})
                combined_params.append(current)

            # Extract the headers - replacing "well known" prefixes as needed
            headers = [k.replace('CONFIG.', '').replace('DEMOGRAPHICS.', '').replace('CAMPAIGN.', '') for k in
                       combined_params[0].keys()]

            # Construct the table
            table = [list(c.values()) for c in combined_params]

            # Initialize the template & create the experiment builder
            tpl = TemplateHelper()
            tpl.set_dynamic_header_table(headers, table)
            tpl.active_templates = list(itertools.chain(*resolved_scenario_template_set.values()))

            experiment_builder = ModBuilder.from_combos(tpl.get_modifier_functions())

            experiment_manager = ExperimentManagerFactory.from_cb(config_builder)
            suite_id = suite_id or experiment_manager.create_suite(suite_name=suite_name)
            experiment_manager.run_simulations(exp_name=scenario_name, exp_builder=experiment_builder,
                                               suite_id=suite_id)
    return suite_id


# Remove NaN-valued keys/parameters from all scenarios dicts. These should be properly interpreted as "No override, run with default value"
# TODO: add support for blank entries for strings?
def remove_nans(scenario_param_dicts):
    cleaned_spds = []
    for spd in scenario_param_dicts:
        cleaned_spd = {}
        for k, v in spd.items():
            try:
                if np.isnan(v):
                    print(f"NaN found for key: {k}")
                else:
                    cleaned_spd[k] = v
            except TypeError:
                cleaned_spd[k] = v  # keep values that can't be parsed
        cleaned_spds.append(cleaned_spd)
    return cleaned_spds


def load_scenario_table(filename):
    # returns a list of parameter dicts, one for each scenario (scenario table row)
    if filename is not None:
        scenario_table = pd.read_csv(filename)
        if 'Campaign' not in scenario_table.columns:
            raise MissingCampaignSpecificationException('Column \'Campaign\' is missing from %s if used' % filename)
        scenario_param_dicts = scenario_table.to_dict(orient='records')
        scenario_param_dicts = remove_nans(scenario_param_dicts=scenario_param_dicts)  # nan values should be mapped to the default value in the config files; don't pass along
        find_and_eval(scenario_param_dicts)  # convert any strings representing lists to actual python lists
    else:
        scenario_param_dicts = [{'Scenario': None, 'Campaign': None}]
    return scenario_param_dicts


def get_samples(args):
    # the provided csv files needs to be in the exact same format as written by resample.py
    samples = pd.read_csv(args.samples_file)
    sample_dicts = samples.to_dict(orient='records')
    try:
        samples = [ParameterSet.from_dict(d) for d in sample_dicts]
    except NaNDetectedError as e:
        e.args = (f"One or more blank entries or lines found in samples file {args.samples_file} . "
                  f"Please fix/remove them. Enjoy this dolphin.\n{DOLPHIN}",)
        raise e
    return samples


def main(args):
    # load scenario information
    load_templates(args.loaded_module)

    # load scenario table if needed - returns a virtually blank dataframe if no load was necessary
    scenario_param_dicts = load_scenario_table(filename=args.scenario_table)

    # now determine the samples to use as the basis for each scenario
    samples = get_samples(args)

    # now run the samples X scenarios simulations
    suite_id = build_and_run_simulations(samples,
                                         scenario_template_sets=args.loaded_module.run_calib_args['scenario_template_sets'],
                                         scenario_param_dicts=scenario_param_dicts,
                                         suite_name=args.suite_name,
                                         loaded_module=args.loaded_module)

    # call the download script if requested
    if not args.no_download:
        print(f'Calling download.py to download suite id: {suite_id} ...')
        dl_args = argparse.Namespace()
        dl_args.suite_id = suite_id
        dl_args.output_path = str(args.output_path)
        dl_args.download_filenames = args.download_filenames
        dl_args.selected_block = args.selected_block
        dl.main(args=dl_args)
    else:
        print(f'No download requested for suite id: {suite_id} , exiting ...')
    print('Done!')


def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--calib-script', dest='calibration_script', type=str, required=True,
                        help='Script used to run the calibration (Required).')
    parser.add_argument('--samples', dest='samples_file', type=str, required=True,
                        help='csv file with user-defined samples to use (Required).')
    parser.add_argument('--no-download', dest='no_download', action='store_true',
                        help='Do not download files after running scenarios (Default: download files).')
    parser.add_argument('-s', '--suite-name', dest='suite_name', type=str, required=True,
                        help='Name of suite for scenario experiment to be run (Required).')
    parser.add_argument('--table', dest='scenario_table', type=str, default=None,
                        help='Scenarios will be generated using a csv table file '
                             '(mutually exclusive with --template-sets).')
    parser.add_argument('--template-sets', dest='template_sets', action='store_true',
                        help='Scenarios will be generated using template sets (mutually exclusive with --table).')
    parser.add_argument('-o', '--output-dir', dest='output_path', type=str, default=dl.DEFAULT_OUTPUT_DIR,
                        help=f'Directory to hold scenario output files (Default: {dl.DEFAULT_OUTPUT_DIR}).')
    parser.add_argument('-f', '--files', dest='download_filenames', type=str, default=dl.DEFAULT_DOWNLOAD_FILES,
                        help=f'Filenames to retrieve from scenario simulations (if downloading). Paths relative to '
                             f'simulation directories. Comma-separated list if more than one '
                             f'(Default: {dl.DEFAULT_DOWNLOAD_FILES}).')
    parser.add_argument('-b', '--block', dest='selected_block', type=str, default=DEFAULT_BLOCK,
                        help=f'simtools.ini block to use (Default: {DEFAULT_BLOCK}).')

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    script_args = parse_args()
    SetupParser.init(selected_block=script_args.selected_block)

    # making sure arguments related to template-set vs table scenario generation are configured properly
    if not ((script_args.scenario_table is None) ^ (script_args.template_sets is False)):
        raise Exception('Must either specify --table FILENAME or --template-sets for scenario generation.')

    if script_args.scenario_table is not None:
        script_args.scenario_mode = SCENARIO_TABLE_MODE
    else:
        script_args.scenario_mode = SCENARIO_TEMPLATE_SETS_MODE

    script_args.loaded_module = load_config_module(script_args.calibration_script)

    n_template_sets = len(script_args.loaded_module.scenario_template_sets)
    if n_template_sets == 0:
        raise Exception('Cannot proceed with zero template sets in provided calibration script.')

    if script_args.scenario_mode == SCENARIO_TABLE_MODE:
        if n_template_sets > 1:
            raise Exception('Exactly one template set (Baseline) must be specified in provided calibration script. There are %d.' % n_template_sets)

    script_args.download_filenames = script_args.download_filenames.strip().split(',')

    main(script_args)
