#!/bin/bash

#SBATCH --nodes=1

#SBATCH --ntasks-per-node=1

#SBATCH --cpus-per-task=1

#SBATCH --time=48:00:00
#SBATCH --partition=a100_short
#SBATCH --mem=8GB

#SBATCH --job-name=naosTest
#SBATCH --chdir=/gpfs/data/bershteynlab/EMOD/yamamn02/ZMB_calib_202206/

#SBATCH --mail-type=END

#SBATCH --mail-user=nao.yamamoto@nyulangone.org

#SBATCH --output=/gpfs/data/bershteynlab/EMOD/yamamn02/ZMB_calib_202206/slurm_%j.out

python run_scenarios.py -c optim_script.py --resample-method provided --samples resampled_parameter_sets.csv --output-dir ZMB_calib_202206 --suite-name ZMB_calib_202206 --table scenarios.csv