import argparse
import os
import subprocess

def main():
    args = parse_args()
    args.window = str(int(float(args.window)))
    input_dir = '/sumstat-data/input/'
    parquet_files = [file for file in os.listdir(input_dir)
                        if os.path.join(input_dir, file).endswith('.parquet')]
    for file in parquet_files:
        print(file)
        cmd = [
            'python',
            '/sumstat-data/filters/significant_window_extraction/filter_by_merge.py',
            '--in_sumstats', os.path.join(input_dir, file),
            '--out_sumstats', os.path.join('/sumstat-data/output/', file),
            '--window', args.window,
            '--pval', args.pval,
            '--data_type', 'gwas'
        ]
        subprocess.call(cmd)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--window', metavar="<integer>",
                        help="Window size", type=str, required=True)
    parser.add_argument('--pval', metavar="<float>",
                        help="p-value", type=str, required=True)
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    main()
