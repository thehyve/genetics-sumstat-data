#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Ed Mountjoy
#
# Requires scipy and pandas

'''
# Set SPARK_HOME and PYTHONPATH to use 2.4.0
export PYSPARK_SUBMIT_ARGS="--driver-memory 8g pyspark-shell"
export SPARK_HOME=/Users/em21/software/spark-2.4.0-bin-hadoop2.7
export PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-2.4.0-src.zip:$PYTHONPATH
'''

import sys
import os
import argparse
from time import time
import pandas
import pyspark.sql
from pyspark.sql.types import *
from pyspark.sql import DataFrame
from pyspark.sql.functions import *
import scipy.stats as st

def main():

    # Args
    args = parse_args()
    args.min_mac = 5
    print(args)

    # # File args (test)
    # args = ArgsPlaceholder()
    # args.study_id = 'Naranbhai_2015'
    # args.in_nominal = '../example_data/Naranbhai_2015/*/*.nominal.sorted.txt.gz'
    # args.in_varinfo = '../example_data/Naranbhai_2015/*/*.variant_information.txt.gz'
    # args.in_gene_meta = '../example_data/*_gene_metadata.txt'
    # args.in_biofeatures_map = '../../../../genetics-backend/biofeatureLUT/biofeature_lut_190208.json'
    # args.out_parquet = '../output/Naranbhai_2015.parquet'

    # Make spark session
    global spark
    spark = (
        pyspark.sql.SparkSession.builder
        .config("parquet.enable.summary-metadata", "true")
        .getOrCreate()
    )
    print('Spark version: ', spark.version)
    start_time = time()

    # Load data and variant table
    data = load_nominal_data(args.in_nominal)
    varinfo = load_variant_info(args.in_varinfo)
    meta = load_gene_metadata(args.in_gene_meta)

    # Filter low quality variants
    varinfo = varinfo.filter(col('mac') >= args.min_mac)

    # Merge
    merged = meta.join(data, on='phenotype_id', how='inner')
    merged = merged.join(varinfo, on=['biofeature_str', 'chrom', 'pos', 'ref', 'alt'])

    # Map biofeature_str to biofeature
    bf_map_dict = spark.sparkContext.broadcast(
        load_biofeatures_map(args.in_biofeatures_map) )
    bf_mapper = udf(lambda key: bf_map_dict.value[key])
    merged = (
        merged.withColumn('bio_feature', bf_mapper(col('biofeature_str')))
              .drop('biofeature_str')
    )

    # Additional columns to match gwas sumstat files
    merged = (
        merged.withColumn('study_id', lit(args.study_id))
              .withColumn('type', lit('eqtl'))
              .withColumn('n_cases', lit(None).cast(IntegerType()))
              .withColumn('mac_cases', lit(None).cast(IntegerType()))
              .withColumn('is_cc', lit(False))
    )

    # Re-order columns
    col_order = [
        'type',
        'study_id',
        'bio_feature',
        'phenotype_id',
        'gene_id',
        'chrom',
        'pos',
        'ref',
        'alt',
        'beta',
        'se',
        'pval',
        'n_total',
        'n_cases',
        'eaf',
        'mac',
        'mac_cases',
        'num_tests',
        'info',
        'is_cc'
    ]
    merged = merged.select(col_order)

    # Repartition and sort
    merged = (
        merged.repartitionByRange('chrom', 'pos')
              .orderBy('chrom', 'pos', 'ref', 'alt')
    )

    # Write output
    (
        merged
        .write
        .partitionBy('bio_feature', 'chrom')
        .parquet(
            args.out_parquet,
            mode='overwrite',
            compression='snappy'
        )
    )

    print('Completed in {:.1f} secs'.format(time() - start_time))

    return 0

def load_biofeatures_map(inf):
    ''' Loads file containing mapping for biofeature_str to code
    Returns:
        python dictionary
    '''

    d = dict(
        spark.read.json(inf)
             .select('biofeature_string', 'biofeature_code')
             .toPandas()
             .values.tolist()
    )

    return d

def load_gene_metadata(pattern):
    ''' Loads the gene meta-data
    '''
    df = (
        spark.read.csv(pattern,
                       sep='\t',
                       inferSchema=True,
                       enforceSchema=True,
                       header=True) )

    # Only keep IDs
    df = (
        df.select('phenotype_id', 'gene_id')
          .distinct()
    )

    return df

def load_variant_info(pattern):
    ''' Loads QTLtools variant info file to spark df
    '''
    df = (
        spark.read.csv(pattern,
                       sep='\t',
                       inferSchema=True,
                       enforceSchema=True,
                       header=False) )

    # Add column names
    cols = ['chrom', 'pos', 'varid', 'ref', 'alt', 'type', 'AC', 'AN', 'MAF',
            'info']
    df = df.toDF(*cols)

    # Calc sample size, EAF, MAC - then drop unneeded
    df = (
        df.withColumn('chrom', col('chrom').cast('string'))
          .withColumn('n_total', (col('AN') / 2).cast('int'))
          .withColumn('eaf', col('AC') / col('AN'))
          .withColumn('mac', least(col('AC'), col('AN') - col('AC')))
          .drop('varid', 'type', 'AC', 'AN', 'MAF')
    )

    # Extract biofeature
    df = df.withColumn('biofeature_str', get_biofeature_udf(input_file_name()))

    # Repartition
    df = df.repartitionByRange('chrom', 'pos')

    return df

def load_nominal_data(pattern):
    ''' Loads QTLtools nominal results file to spark df
    '''
    df = (
        spark.read.csv(pattern,
                       sep='\t',
                       inferSchema=True,
                       enforceSchema=True,
                       header=False) )
    # Add column names
    cols = ['phenotype_id', 'pheno_chrom', 'pheno_start', 'pheno_end',
            'pheno_strand', 'num_tests', 'tss_dist', 'var_id',
            'chrom', 'pos', 'var_null', 'pval', 'beta', 'is_sentinal']
    df = df.toDF(*cols)

    # Split alleles
    parts = split(df.var_id, '_')
    df = (
        df.withColumn('ref', parts.getItem(2))
          .withColumn('alt', parts.getItem(3))
    )

    # Calculate standard errors
    df = (
        df.withColumn('z_abs', abs(ppf_udf(col('pval'))))
          .withColumn('se', abs(col('beta')) / col('z_abs'))
          .drop('z_abs')
    )

    # Add biofeature
    df = df.withColumn('biofeature_str', get_biofeature_udf(input_file_name()))

    # Clean fields
    df = (
        df.drop('var_null', 'pheno_strand', 'pheno_chrom', 'pheno_start',
                'pheno_end', 'var_id')
          .withColumn('chrom', df.chrom.cast('string'))
          .withColumn('is_sentinal', df.is_sentinal.cast('boolean'))
          .select(['phenotype_id', 'biofeature_str', 'chrom', 'pos', 'ref',
                   'alt', 'pval', 'beta', 'se', 'num_tests'])
    )

    # Repartition
    df = df.repartitionByRange('chrom', 'pos')

    return df

def get_biofeature(filename):
    ''' Returns biofeature from filename
    '''
    return filename.split('/')[-1].split('.')[0]
get_biofeature_udf = udf(get_biofeature, StringType())

def ppf(pval):
    ''' Return inverse cumulative distribution function of the normal
        distribution. Needed to calculate stderr.
    '''
    return float(st.norm.ppf(pval / 2))
ppf_udf = udf(ppf, DoubleType())

class ArgsPlaceholder():
    pass

def parse_args():
    """ Load command line args """
    parser = argparse.ArgumentParser()
    parser.add_argument('--study_id', metavar="<file>", help=('Study ID to add as column'), type=str, required=True)
    parser.add_argument('--in_nominal', metavar="<file>", help=('Input sum stats'), type=str, required=True)
    parser.add_argument('--in_varinfo', metavar="<file>", help=("Input variant information"), type=str, required=True)
    parser.add_argument('--in_gene_meta', metavar="<file>", help=("Input gene meta-data"), type=str, required=True)
    parser.add_argument('--in_biofeatures_map', metavar="<file>", help=("Input biofeature to ontology map"), type=str, required=True)
    parser.add_argument('--out_parquet', metavar="<file>", help=("Output parquet path"), type=str, required=True)
    args = parser.parse_args()
    return args

if __name__ == '__main__':

    main()
