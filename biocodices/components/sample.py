import pandas as pd
from os import makedirs
from os.path import isdir, join, isfile
from datetime import datetime
from termcolor import colored

from biocodices.variant_calling import ReadsMunger, VcfMunger
from biocodices.helpers.language import seconds_to_hms_string
from biocodices.helpers import Config


class Sample:
    reads_format = 'fastq'

    def __init__(self, sample_id, cohort):
        """
        Expects a sample_id and a Cohort object.
        It will look for its fastq files in the cohort.data_dir with
        filenames like: <sample_id>.R1.fastq, <sample_id>.R2.fastq
        (for the forward and reverse reads, respectively).
        """
        self.id = sample_id
        self.cohort = cohort
        self.results_dir = join(self.cohort.results_dir, self.id)
        self._set_data()

    def __repr__(self):
        return '<Sample {} from {}>'.format(self.id, self.sequencer_run_id)

    def call_variants(self, trim_reads=True, align_reads=True,
                      create_vcfs=True):
        if not isdir(self.results_dir):
            makedirs(self.results_dir, exist_ok=True)

        t1 = datetime.now()
        print(colored('* {}'.format(self.long_name), 'yellow'))
        print('Result files and logs will be put in:')
        print(self.results_dir, '\n')

        if trim_reads:
            self.analyze_and_trim_reads()
        if align_reads:
            self.align_reads()
            self.process_alignment_files()
            self.alignment_metrics()
        if create_vcfs:
            self.create_variant_files()

        t2 = datetime.now()
        self._log_total_time(t1, t2)
        print()

    def analyze_and_trim_reads(self):
        for reads_filepath in self.fastqs:
            self.reads_munger.analyze_reads(reads_filepath)

        self.reads_munger.trim_adapters(self.fastqs)

        for trimmed_filepath in self.trimmed_fastqs:
            self.reads_munger.analyze_reads(trimmed_filepath)

    def align_reads(self):
        self.reads_munger.align_to_reference(self.trimmed_fastqs)

    def process_alignment_files(self):
        self.reads_munger.add_or_replace_read_groups(self)

        #  remove(self._files('sam'))

        self.reads_munger.realign_reads_around_indels(self.bam)

        self.reads_munger.recalibrate_quality_scores(self.realigned_bam)

    def alignment_metrics(self):
        self.reads_munger.generate_alignment_metrics(self.recalibrated_bam)

        self.get_median_coverage()

    def get_median_coverage(self):
        self.depth_vcf = self._files('realigned.recalibrated.depth_stats.vcf')
        if not isfile(self.depth_vcf):
            self.depth_vcf = self.reads_munger.depth_vcf(self.recalibrated_bam)
        depth_stats = VcfMunger.read_depth_stats_vcf(self.depth_vcf)
        return pd.Series(depth_stats).median()

    def create_gvcf(self):
        self.raw_gvcf = self.reads_munger.create_gvcf(self.recalibrated_bam)
        return self.raw_gvcf

    def create_vcf(self):
        self.raw_vcf = self.reads_munger.create_vcf(self.recalibrated_bam)
        return self.raw_vcf

    def read_alignment_metrics(self):
        # This is called by the sample's Cohort to plot everything together.
        fn = self._files('realigned.recalibrated.alignment_metrics.tsv')
        df = pd.read_table(fn, sep='\s+', comment='#')
        df['sample'] = self.id
        return df

    #  def read_variant_calling_metrics(self):
        #  # This is called by the sample's Cohort to plot everything together.
        #  fn = self._files('')
        #  df = pd.read_table(fn, sep='\s+', comment='#')
        #  df['sample'] = self.id
        #  return df

    def log(self, extension):
        return join(self.results_dir, '{}.{}.log'.format(self.id, extension))

    def msg(self, msg):
        prefix = colored('[{}]'.format(self.id), 'cyan')
        return '{} {}'.format(prefix, msg)

    def _log_total_time(self, t1, t2):
        elapsed = seconds_to_hms_string((t2 - t1).seconds)
        with open(self.log('time'), 'w') as logfile:
            msg = 'Variant calling for {} took {}.\n'
            logfile.write(msg.format(self.id, elapsed))

    def _files(self, ext):
        if ext in ['fastq', 'trimmed.fastq']:
            return self._reads_files(ext)

        return '{}.{}'.format(join(self.results_dir, self.id), ext)

    def _reads_files(self, ext):
        location = self.cohort.data_dir
        if ext == 'trimmed.fastq':
            location = self.results_dir
        read_filepath = join(location, '{}.{}.{}')
        forward_filepath = read_filepath.format(self.id, 'R1', ext)
        reverse_filepath = read_filepath.format(self.id, 'R2', ext)
        if ext == 'fastq':
            if not isfile(forward_filepath) or not isfile(reverse_filepath):
                msg = "I couldn't find BOTH R1 and R2 reads: {}, {}"
                raise OSError(msg.format(forward_filepath, reverse_filepath))

        return forward_filepath, reverse_filepath

    def _get_library_id(self):
        try:
            return Config('db')[self.id][0]
        except KeyError:
            return self.cohort.id

    def _get_seq_run_id(self):
        try:
            return Config('db')[self.id][1]
        except KeyError:
            return self.cohort.id

    def _get_name(self):
        try:
            return Config('db_names')[self.id][0]
        except KeyError:
            return self.id

    def _get_clinic(self):
        try:
            return Config('db_names')[self.id][1]
        except KeyError:
            return 'unknown clinic'

    def _set_data(self):
        self.library_id = self._get_library_id()
        self.sequencer_run_id = self._get_seq_run_id()
        self.name = self._get_name()
        self.clinic = self._get_clinic()
        self.long_name = '{} ({}) from {}'.format(
            self.name, self.id, self.clinic)
        self.reads_munger = ReadsMunger(self.results_dir)
        self.vcf_munger = VcfMunger()
        self.fastqs = self._files('fastq')
        self.trimmed_fastqs = self._files('trimmed.fastq')
        self.sam = self._files('sam')
        self.bam = self._files('bam')
        self.realigned_bam = self._files('realigned.bam')
        self.recalibrated_bam = self._files('realigned.recalibrated.bam')
        self.raw_vcf = self._files(Config.filenames['sample_raw_vcf_suffix'])
        self.raw_gvcf = self._files(Config.filenames['sample_raw_gvcf_suffix'])
        self.filtered_vcf = \
            self._files(Config.filenames['sample_filtered_vcf_suffix'])
