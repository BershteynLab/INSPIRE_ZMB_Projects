#!/bin/bash

#SBATCH --nodes=1

#SBATCH --ntasks-per-node=1

#SBATCH --cpus-per-task=1

#SBATCH --time=4:00:00
#SBATCH --partition=a100_dev
#SBATCH --mem=8GB

#SBATCH --job-name=Zam
#SBATCH --chdir=/gpfs/data/bershteynlab/EMOD/kaftad01/ZMB_calib_202206

#SBATCH --mail-type=END

#SBATCH --mail-user=kaftand@gmail.com

#SBATCH --output=/gpfs/data/bershteynlab/EMOD/kaftad01/ZMB_calib_202206/slurm_%j.out

python run_scenarios.py -c optim_script.py --resample-method provided --samples resampled_parameter_sets_LITE.csv --output-dir test_art_issue --suite-name ZMB_calib_202206 --table scenarios_baseline.csv