from os import makedirs, remove
from os.path import isdir, join, isfile
from datetime import datetime
from termcolor import colored

from biocodices.variant_calling.reads_munger import ReadsMunger
from biocodices.helpers.helpers import seconds_to_hms_string


class Sample:
    reads_format = 'fastq'

    def __init__(self, sample_id, sequencing):
        """
        Expects a sample_id and a Sequencing object.
        It will look for its fastq files in the sequencing.data_dir with
        filenames like: <sample_id>.R1.fastq, <sample_id>.R2.fastq
        (for the forward and reverse reads, respectively).
        """
        self.id = sample_id
        self.sequencing = sequencing
        self.results_dir = join(self.sequencing.results_dir, self.id)
        self.reads_munger = ReadsMunger(self, self.results_dir)

    def __repr__(self):
        return '<Sample {} from {}>'.format(self.id, self.sequencing.id)

    def call_variants(self):
        if not isdir(self.results_dir):
            makedirs(self.results_dir, exist_ok=True)

        t1 = datetime.now()
        print('Calling variants for ' + colored('{}'.format(self.id), 'yellow'))
        print('Result files and logs will be put in:')
        print(self.results_dir, '\n')

        self.printlog('Analyze reads')
        for reads_filepath in self._files('fastq'):
            self.reads_munger.analyze_reads(reads_filepath)

        self.printlog('Trim adapters')
        self.reads_munger.trim_adapters(self._files('fastq'))

        self.printlog('Analyze trimmed reads')
        for trimmed_filepath in self._files('trimmed.fastq'):
            self.reads_munger.analyze_reads(trimmed_filepath)

        # TODO: implement this
        # self.reads_munger.multiqc(self._files('fastq') + self._files('trimmed.fastq'))

        self.printlog('Align reads to reference')
        self.reads_munger.align_to_reference(self._files('trimmed.fastq'))

        self.printlog('Add or replace read groups')
        self.reads_munger.add_or_replace_read_groups(self)

        self.printlog('Delete sam file')
        #  remove(self._files('sam'))

        self.printlog('Realign indels')
        self.reads_munger.realign_indels(self._files('bam'))

        self.printlog('Recalibrate read quality scores')
        self.reads_munger.recalibrate_quality_scores(self._files('bam'))

        self.printlog('Call variants')
        self.reads_munger.call_variants(self._files('bam'))

        t2 = datetime.now()
        self._log_total_time(t1, t2)

    def log(self, extension):
        return join(self.results_dir, '{}.{}.log'.format(self.id, extension))

    def printlog(self, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = colored('[{}][{}]'.format(timestamp, self.id), 'blue')
        print('{} {}'.format(prefix, msg))

    def _log_total_time(self, t1, t2):
        elapsed = seconds_to_hms_string((t2 - t1).seconds)
        with open(self.log('time'), 'w') as logfile:
            msg = 'Variant calling for {} took {}.\n'
            logfile.write(msg.format(self.id, elapsed))

    def _files(self, ext):
        if ext in ['fastq', 'trimmed.fastq']:
            setattr(self, ext, self._reads_files(ext))
            return getattr(self, ext)

        filepath = '{}.{}'.format(join(self.results_dir, self.id), ext)
        setattr(self, ext, filepath)
        return getattr(self, ext)

    def _reads_files(self, ext):
        location = self.sequencing.data_dir
        if ext == 'trimmed.fastq':
            location = self.results_dir
        read_filepath = join(location, '{}.{}.{}')
        forward_filepath = read_filepath.format(self.id, 'R1', ext)
        reverse_filepath = read_filepath.format(self.id, 'R2', ext)
        if not isfile(forward_filepath) or not isfile(reverse_filepath):
            msg = "I couldn't find BOTH R1 and R2 reads: {}, {}"
            raise OSError(msg.format(forward_filepath, reverse_filepath))

        return forward_filepath, reverse_filepath
