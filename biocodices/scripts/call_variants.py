#!/usr/bin/env python

import sys
from itertools import product
from termcolor import colored
from os import makedirs
from os.path import expanduser, dirname, join, exists
from biocodices import Sequencing, software_name


def call_variants_for_all_samples(base_dir):
    sequencing = Sequencing(expanduser(base_dir))
    samples = sequencing.samples()

    print(biocodices_logo())
    print('Welcome to {}! Anlyzing reads for:'.format(software_name))
    print(colored(sequencing, 'green'))
    print('\nYou can follow the details of the process with:')
    print('`tail -f {}/*/*.log`\n'.format(sequencing.results_dir))

    dir_list = [sample.results_dir for sample in samples]
    touch_all_the_logs(dir_list)

    for sample in samples:
        sample.call_variants()
        print()

    print(colored('\nDone! Bless your heart.\n', 'green'))


def touch_all_the_logs(dir_list):
    # I wrote this just to be able to run a `tail -f *.log` on every log
    # during the variant calling, even for logs that don't yet exist but that
    # will be created during the process. It's a necessarily hardcoded list,
    # I guess:
    [makedirs(d, exist_ok=True) for d in dir_list]
    logs = ['AddOrReplaceReadGroups', 'BaseRecalibrator', 'bwa', 'fastqc',
            'fastq-mcf', 'HaplotypeCaller_gvcf', 'HaplotypeCaller_vcf',
            'IndelRealigner', 'PrintReads', 'RealignerTargetCreator']
    log_filepaths = [join(d, fn + '.log') for d, fn in product(dir_list, logs)]
    for log_filepath in log_filepaths:
        if not exists(log_filepath):
            open(log_filepath, 'a').close()


def biocodices_logo():
    with open(join(dirname(__file__), 'logo.txt'), 'r') as logo_file:
        logo_string = logo_file.read()
    return logo_string


if __name__ == '__main__':
    args = sys.argv
    if len(args) != 2:
        print('\nUsage:')
        print('{} <root dir of sequencing>'.format(__file__))
        sys.exit()

    base_dir = args[1]
    call_variants_for_all_samples(base_dir)
