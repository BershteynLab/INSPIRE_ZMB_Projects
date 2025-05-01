#!/bin/bash

#SBATCH --nodes=1

#SBATCH --ntasks-per-node=1

#SBATCH --cpus-per-task=1

#SBATCH --time=4:00:00
#SBATCH --partition=a100_dev
#SBATCH --mem=8GB

#SBATCH --job-name=ZMB
#SBATCH --chdir=/gpfs/data/bershteynlab/EMOD/citrod01/ZMB_calib_202206
#SBATCH --mail-type=END

#SBATCH --mail-user=daniel.citron@nyulangone.org

#SBATCH --output=/gpfs/data/bershteynlab/EMOD/citrod01/ZMB_calib_202206/slurm_%j.out

python -m hiv.scripts.run_scenarios -c optim_script.py --resample-method provided --samples resampled_parameter_sets_short.csv --output-dir v17 --suite-name ZMB_calib_202206 --table scenarios.csv -b NYUCLUSTER