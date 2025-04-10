#!/bin/bash

#SBATCH --nodes=1

#SBATCH --ntasks-per-node=1

#SBATCH --cpus-per-task=1

#SBATCH --time=4:00:00
#SBATCH --partition=a100_dev
#SBATCH --mem=8GB

#SBATCH --job-name=Zam
#SBATCH --chdir=/gpfs/data/bershteynlab/EMOD/kimh47/ZMB_calib_202206

#SBATCH --mail-type=END

#SBATCH --mail-user=hae-young.kim@nyulangone.org

#SBATCH --output=/gpfs/data/bershteynlab/EMOD/kimh47/ZMB_calib_202206/slurm_%j.out

python -m hiv.scripts.run_scenarios -c optim_script.py --resample-method provided --samples resampled_parameter_sets_2.csv --output-dir v17 --suite-name ZMB_calib_202206 --table scenarios_HK.csv -b NYUCLUSTER