from os.path import dirname, join

from biocodices.helpers import Config, Resource
from biocodices.programs import AbstractGenomicsProgram, ProgramCaller


class BcfTools(AbstractGenomicsProgram):
    def __init__(self):
        self.label = 'bcftools'
        super(self.__class__, self).__init__(self.label)

    def run(self, module_name, infile, outfile, params_str=None,
            log_label=None):
        command = '{} {} {} {}'.format(self.executable, module_name,
                                       (params_str or ''), infile)
        log_label = log_label or '{}_{}'.format(self.label, module_name)
        log_filepath = join(dirname(outfile), log_label)
        ProgramCaller(command).run(stdout_sink=outfile,
                                   log_filepath=log_filepath)

    def subset_samples(self, vcf_path, sample_ids, outfile):
        """
        Makes a new VCF keeping the columns you specify.
        - vcf_path: an absolute path to a [g]VCF file.
        - sample_ids: a list of the columns (i.e. samples ids) to keep.
        - outfile: an absolute path for the new vcf file.
        """
        params_str = '--samples ' + ','.join(sample_ids)
        self.run('view', vcf_path, outfile, params_str=params_str,
                 log_label='bcftools_view_samples')
        return outfile

    def limit_regions(self, gzipped_vcf_path, out_path=None):
        """
        Subset a VCF.gz keeping the regions contained in the BED defined as
        'panel_amplicons' in the resources.yml file. Output a VCF.
        """
        outfile = out_path or gzipped_vcf_path.replace('.vcf.gz', '.lim.vcf')
        params_str = '--regions-file {}'.format(Resource('panel_amplicons'))
        self.run('view', gzipped_vcf_path, outfile, params_str=params_str,
                 log_label='bcftools_view_regions')
        return outfile

    @classmethod
    def compress_and_index_vcf(cls, vcf_path):
        """Just a shortcut that calls bgzip and tabix on a VCF file. The output
        is a gzipped vcf with an index file alongside, so that BcfTools can
        use it."""
        gzipped_vcf_path = cls.bgzip(vcf_path)
        cls.tabix(gzipped_vcf_path)
        return gzipped_vcf_path

    @staticmethod
    def tabix(gzipped_vcf_path):
        """Index a bgzip-zipped VCF.gz to let some bcftools modules use it."""
        executable = Config.executables['tabix']
        command = '{} {}'.format(executable, gzipped_vcf_path)
        log_filepath = join(dirname(gzipped_vcf_path), 'tabix')
        ProgramCaller(command).run(log_filepath=log_filepath)
        return gzipped_vcf_path

    @staticmethod
    def bgzip(vcf_path):
        """Zips a VCF to vcf.gz to let some bcftools modules use it."""
        executable = Config.executables['bgzip']
        outfile = vcf_path.replace('.vcf', '.vcf.gz')
        command = '{} -ci {}'.format(executable, vcf_path)
        log_filepath = join(dirname(outfile), 'bgzip')
        ProgramCaller(command).run(stdout_sink=outfile,
                                   log_filepath=log_filepath)
        return outfile
