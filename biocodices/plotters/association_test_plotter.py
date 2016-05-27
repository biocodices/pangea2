import numpy as np
import seaborn as sns

from biocodices.plotters.base_plotter import BasePlotter


class AssociationTestPlotter(BasePlotter):
    def __init__(self, association_tester, plots_dir=None):
        self.assoc = association_tester
        self.base_dir = plots_dir
        if plots_dir is None:
            self.base_dir = self.assoc.dataset.dir

    def draw_p_values(self, series, ax, max_p=0.05,
                      threshold_lines=[0.05, 0.01, 0.001]):
        """
        Takes a series of p-values indexed by chromosome and rs_ID.
        Plots the p-values below the 'max_p' threshold (choose 0 to plot
        all the p-values).
        """
        p_values = series[series < max_p]
        if p_values.empty:
            print('No p values smaller than {} found'.format(max_p))
            return

        ax = p_values.plot(linestyle='', marker='o', markersize=4, logy=True,
                           color='indigo')
        ax.invert_yaxis()
        ax.set_ylabel('p-value')
        xtick_labels = str(p_values.index.values)
        ax.set_xticks(np.arange(len(xtick_labels)))
        ax.set_xticklabels(xtick_labels, rotation=90)

        for threshold in threshold_lines:
            ax.text(y=threshold, x=0, s='$p = {}$'.format(threshold),
                    color='red')
            ax.axhline(threshold, linewidth=0.5, color='red')

        sns.despine(left=True)
        ax.xaxis.grid()
        return ax

    #  def draw_ax(self, ax, tests_to_plot, significance=0.05):
        #  df = self.assoc.result.sort_values(by=['CHR', 'BP'])
        #  palette_name = Config('plots')['assoc']['palette_name']
        #  colors = sns.color_palette(palette_name, len(tests_to_plot))
        #  for test in tests_to_plot:
            #  marker = '.' if test == 'UNADJ' else 'o'
            #  df[test].plot(ax=ax, marker=marker, linestyle='', logy=True,
                          #  label=test, color=colors.pop(0), linewidth=1)
        #  ax.invert_yaxis()
        #  ax.axhline(significance, linestyle='solid', color='green',
                   #  linewidth=1)
        #  ax.text(1, significance, '$P = {}$'.format(significance),
                #  color='green')
        #  ax.set_xlabel('')
        #  ax.set_xticks(np.arange(len(df.index)))
        #  ax.set_xticklabels(df.index, rotation=90)
        #  sns.despine(left=True)
        #  ax.legend()
        #  return ax
