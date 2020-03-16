#!/bin/sh

#SBATCH --qos=normal
#SBATCH --time=3000
#SBATCH --mem=50G
#SBATCH --job-name=neural_sketch
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:titan-x:1


#export PATH=/om/user/mnye/miniconda3/bin/:$PATH
#source activate /om/user/mnye/vhe/envs/default/
#cd /om/user/mnye/vhe
which python
anaconda-project run $@
