#train_and_test.sh
#script to train and test model


if [[ "$@" == "--inner" ]]; then

	which python

	#Only pretrain
	RES_PRE=$(sbatch --parsable -e 'pretrain.out' -o 'pretrain.out' execute_gpu.sh python train/main_supervised_algolisp.py --exclude_gt --use_dataset_len 8000 --pretrain --max_epochs 0 --max_pretrain_epochs 45 --train_to_convergence)
	echo "pretraining job: $RES_PRE"

	# train dc_model:
	RES_DC=$(sbatch --parsable -e 'dctrain.out' -o 'dctrain.out' execute_gpu.sh python train/algolisp_train_dc_model.py --exclude_gt --use_dataset_len 8000 --max_epochs 25 --inv_temp 0.05 --nHoles 3 -k 50)
 	echo "dc model training job: $RES_DC"

	# train model:
	RES_TRAIN=$(sbatch --parsable --dependency=afterok:$RES_PRE -e 'train.out' -o 'train.out' execute_gpu.sh python train/main_supervised_algolisp.py --exclude_gt --use_dataset_len 8000 --train_to_convergence --max_epochs 45 --use_dc_grammar './saved_models/algolisp_dc_model.p' --inv_temp 0.25 --nHoles 3 -k 50 --use_timeout)

	echo "eval geq jobs"
	sbatch --dependency=afterok:$RES_TRAIN -e 'finaleval.out' -o 'finaleval.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --gt --mdl 100 --queue --n_processes 44 --timeout 600 --max_to_check 20000 --resultsfile "results_model"

	sbatch --dependency=afterok:$RES_PRE -e 'finalevalrnn.out' -o 'finalevalrnn.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --gt --mdl 100 --model_path "./saved_models/algolisp_pretrained.p" --resultsfile "results_rnn_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000
	
	sbatch --dependency=afterok:$RES_DC -e 'finalevaldc.out' -o 'finalevaldc.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --gt --mdl 100 --dc_baseline --resultsfile "results_dc_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000


	echo "eval leq jobs"
	sbatch --dependency=afterok:$RES_TRAIN -e 'finalevallt.out' -o 'finalevallt.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --lt --mdl 100 --queue --n_processes 44 --timeout 600 --max_to_check 20000 --resultsfile "results_model"

	sbatch --dependency=afterok:$RES_PRE -e 'finalevalrnnlt.out' -o 'finalevalrnnlt.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --lt --mdl 100 --model_path "./saved_models/algolisp_pretrained.p" --resultsfile "results_rnn_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000
	
	sbatch --dependency=afterok:$RES_DC -e 'finalevaldclt.out' -o 'finalevaldclt.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --lt --mdl 100 --dc_baseline --resultsfile "results_dc_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000

	#echo "dev jobs:"
	# test model
	#sbatch --dependency=afterok:$RES_TRAIN -e 'finaldev.out' -o 'finaldev.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --odd --dataset 'dev' --n_test 696 --mdl 100 --queue --n_processes 44 --timeout 600 --max_to_check 20000 --resultsfile "results_dev_model"

	#batch --dependency=afterok:$RES_PRE -e 'finaldevrnn.out' -o 'finaldevrnn.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --odd --dataset 'dev' --n_test 696 --mdl 100 --model_path "./saved_models/algolisp_pretrained.p" --resultsfile "results_dev_rnn_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000
	
	#sbatch --dependency=afterok:$RES_DC -e 'finaldevdc.out' -o 'finaldevdc.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --odd --dataset 'dev' --n_test 696 --mdl 100 --dc_baseline --resultsfile "results_dev_dc_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000

else
	#to activate, should properly run:
	echo "running main script at run.txt"
	name=algolisp_excludegt_8k g-run bash train_and_test_excludegt.sh --inner > run.txt & #can i do this??
fi

#sbatch -e 'evalrnn.out' -o 'evalrnn.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --n_test 8995 --only_passable --model_path "./saved_models/algolisp_pretrained.p" --resultsfile "results_rnn_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000

#sbatch -e 'evaldevprelim.out' -o 'evaldevprelim.out' execute_public_cpu.sh python eval/evaluate_algolisp.py --dataset 'dev' --n_test 9807 --only_passable --queue --n_processes 44 --timeout 600 --max_to_check 20000 --resultsfile "results_dev_model_prelim"


#sbatch -e 'finalevaleven.out' -o 'finalevaleven.out' execute_cpu.sh python eval/evaluate_algolisp.py --even --n_test 638 --mdl 100 --queue --n_processes 44 --timeout 600 --max_to_check 20000 --resultsfile "results_model"

#sbatch -e 'finalevalrnneven.out' -o 'finalevalrnneven.out' execute_cpu.sh python eval/evaluate_algolisp.py --even --n_test 638 --mdl 100 --model_path "./saved_models/algolisp_pretrained.p" --resultsfile "results_rnn_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000
	
#sbatch -e 'finalevaldceven.out' -o 'finalevaldceven.out' execute_cpu.sh python eval/evaluate_algolisp.py --even --n_test 638 --mdl 100 --dc_baseline --resultsfile "results_dc_base" --queue --n_processes 44 --timeout 600 --max_to_check 20000
