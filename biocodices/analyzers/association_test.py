import pandas as pd
import matplotlib.pyplot as plt

from biocodices.plotters.association_test_plotter import AssociationTestPlotter


class AssociationTest:
    def __init__(self, dataset):
        self.dataset = dataset
        self.plotter = AssociationTestPlotter(self, self.dataset.dir)

    def __repr__(self):
        return '<{} for {}>'.format(self.__class__.__name__,
                                    self.dataset.label)

    def run(self):
        self.result = {}
        tests = {}
        tests['UNADJ'] = self.dataset.plink.assoc(adjust=False)
        tests['ADJUST'] = self.dataset.plink.assoc(adjust=True)
        tests['model'] = self.dataset.plink.model()

        for test_name, test_filename in tests.items():
            df = pd.read_table(test_filename, sep='\s+').set_index('SNP')
            self.result[test_name] = df

        # Split the single table with all models into different tables
        for model_name, df in self.result['model'].groupby('TEST'):
            self.result[model_name] = df
        del(self.result['model'])

    # FIXME: needs rewriting
    #  def plot(self, ax=None, tests_to_plot=None):

        #  if ax is None:
            #  _, ax = plt.subplots(figsize=(15, 5))

        #  if tests_to_plot is None:
            #  tests_to_plot = self.available_tests

        #  self.plotter.draw_ax(ax, tests_to_plot)
        #  return ax

    #  def plot_models(self, ax=None):
        #  if ax is None:
            #  _, ax = plt.subplots(figsize=(15, 5))

        #  for model in self.available_models:
            #  df = getattr(self, model)
            #  df.rename(columns={'P': model})
            #  self.plotter.draw_ax(ax, tests_to_plot=[model])

        #  return ax