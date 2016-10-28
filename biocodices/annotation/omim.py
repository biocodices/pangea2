import re
import time
import requests
from multiprocessing import Pool
from functools import lru_cache

import pandas as pd
from bs4 import BeautifulSoup

from biocodices.helpers import randomize_sleep_time
from biocodices.annotation import AnnotatorWithCache


class Omim(AnnotatorWithCache):
    @staticmethod
    def _key(mim_id):
        return 'omim:%s' % mim_id

    @staticmethod
    @lru_cache()
    def _make_soup(html):
        return BeautifulSoup(html, 'html.parser')

    @staticmethod
    def _url(mim_id):
        return 'http://omim.org/entry/{0}'.format(mim_id)

    @classmethod
    def _query(cls, mim_id):
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) ' + \
                     'AppleWebKit/537.36 (KHTML, like Gecko) ' + \
                     'Chrome/39.0.2171.95 Safari/537.36'

        response = requests.get(cls._url(mim_id),
                                headers={'user-agent': user_agent})
        if not response.ok:
            print(response.status_code, 'status code for id "{0}"'.format(mim_id))

        return response.text

    def _batch_query(self, mim_ids, parallel, sleep_time):
        html_dict = {}

        # OMIM seems to be very strict against web crawlers and bans IPs.
        # That's why we override the _batch_query method and avoid
        # parallelization here.
        # Never ommit the sleeping step between queries, and never let it
        # be less than a couple of seconds, just in case:
        if sleep_time < 3:
            sleep_time = 3

        for i, mim_id in enumerate(mim_ids):
            if i > 0:
                # To further simulate real human behavior when visiting the page,
                # randomize the sleeping time:
                random_sleep_time = randomize_sleep_time(sleep_time)
                print('  Random sleep: {0:.2f} seconds'.format(random_sleep_time))
                time.sleep(random_sleep_time)

            print('[%s/%s] Visit %s' % (i+1, len(mim_ids), self._url(mim_id)))
            html = self._query(mim_id)
            self._cache_set({mim_id: html})
            html_dict[mim_id] = html

        return html_dict

    @classmethod
    def parse_html_dict(cls, html_dict):
        """
        Parses a dict like { '60555': '<html ...>' }. Meant for the result
        of #annotate() for this class. Returns a DataFrame of OMIM variants.
        """
        variants = cls._parallel_parse_html_dict(
                cls._extract_variants_from_html, html_dict)
        references = cls._parallel_parse_html_dict(
                cls._extract_references_from_html, html_dict)
        phenotypes = cls._parallel_parse_html_dict(
                cls._extract_phenotypes_from_html, html_dict)

        # Add the corresponding references found in the page to each variant
        for variant in variants:
            pmids = [pmid for pmid in variant['pubmeds_summary'].values() if pmid]
            variant['pubmeds'] = [ref for ref in references
                                if 'pmid' in ref and ref['pmid'] in pmids]

            variant_phenotypes = [pheno for pheno in phenotypes
                                        for pheno_id in variant['phenotype_ids']
                                        if pheno['id'] == pheno_id]
            variant['phenotypes'] = (variant_phenotypes or None)

        df = pd.DataFrame(variants)

        if not df.empty:
            df['rs'] = df['variant'].str.findall(r'dbSNP:(rs\d+)').str.join('|')

            prot_regex = r'\w+, (.+?)(?:,| \[| -| \()'
            df['prot_change'] = df['variant'].str.extract(prot_regex, expand=False)

        return df

    @classmethod
    def _parallel_parse_html_dict(cls, parse_function, html_dict):
        ret = []
        with Pool(8) as pool:
            results = [pool.apply_async(parse_function, (html, ))
                       for html in html_dict.values()]
            for result in results:
                ret += (result.get() or [])

        return ret

    @classmethod
    def _extract_references_from_html(cls, html):
        soup = cls._make_soup(html)
        references = []

        in_the_references_section = False
        for td in soup.select('td#floatingEntryContainer .wrapper-table td'):
            if not in_the_references_section:
                # Check again if the section started:
                in_the_references_section = (td.get('id') == 'references')
                continue

            # Get in the references section
            for td2 in td.select('.wrapper-table td.text'):
                if td2.get('id') and 'reference' in td2.get('id'):
                    continue

                fields = ['authors', 'title', 'publication', 'pubmed_str']
                values = [span.text.strip() for span in td2.select('span')]
                reference = dict(zip(fields, values))

                if 'pubmed_str' in reference:
                    pubmed_match = re.search(r'PubMed: (\d+)',
                                             reference['pubmed_str'])
                    if pubmed_match:
                        reference['pmid'] = pubmed_match.group(1)
                    del(reference['pubmed_str'])

                references.append(reference)

            break  # Leaving the references section, ignore the rest of <td>s

        return references

    @classmethod
    def _extract_phenotypes_from_html(cls, html):
        """
        Parse the HTML of an OMIM Entry page for a gene and return a list of
        phenotype dictionaries with name and id keys.
        """
        soup = cls._make_soup(html)

        # Find the table title and advance to the next element
        table_title = soup.select('td#geneMap')

        if not table_title:  # Usually means we're in a Phenotype entry
            return []

        table_title = table_title[0]
        next_sib = [element for element in table_title.parent.next_siblings
                    if element != '\n'][0]

        phenotypes = []
        fields = 'name', 'id', 'inheritance', 'key'

        for tr in next_sib.select('.embedded-table tr')[1:]:  # Skips header
            row = [td.text.strip() for td in tr.select('td')
                   if 'rowspan' not in td.attrs]  # Skips Location column
            phenotype = dict(zip(fields, row))
            phenotypes.append(phenotype)

        return phenotypes


    @classmethod
    def _extract_variants_from_html(cls, html):
        """
        Parses the HTML of an OMIM Gene Entry. Returns a list of variant
        entries found in the page.
        """
        html = html.replace('<br>', '<br/>')
        # ^ Need this so the parser doesn't think what comes after a <br>
        # is the <br>'s children. Added it to keep the newlines in OMIM
        # review texts.

        soup = cls._make_soup(html)

        omim_id = soup.select('span#title')[0].text.strip()
        if '*' not in omim_id:  # * signals a GeneEntry
            return None
        omim_id = omim_id.replace('*', '')

        name_symbol = re.split(r';\s*', soup.select('td.title')[0].text.strip())
        if len(name_symbol) == 1:
            gene_name = name_symbol[0]
            hgcn_text = soup.select('td.subheading.italic.bold.text-font')
            if hgcn_text:
                gene_symbol = hgcn_text[0].text.split(': ')[-1]
        else:
            gene_name, gene_symbol = name_symbol

        entries = []
        current_entry = {}

        in_the_variants_section = False
        table_rows = soup.select('td#floatingEntryContainer .wrapper-table td')
        for td in [td for td in table_rows if td.text]:
            inner_text = re.sub(r'\s+', ' ', td.text).strip()

            # Detect start and end of the ALLELIC VARIANTS section
            if not in_the_variants_section:
                in_the_variants_section = re.search(r'Table View', inner_text)
                continue
            elif re.search(r'REFERENCES', inner_text):
                entries.append(current_entry) if current_entry else None
                break

            # Title of new entry
            title_match = re.match(r'\.(\d{4}) (.+)', inner_text)
            if title_match:
                entries.append(current_entry) if current_entry else None

                if not re.search(r'REMOVED FROM|MOVED TO', inner_text):
                    current_entry = {
                            'sub_id': title_match.group(1),
                            'phenotype_names': [title_match.group(2)]
                    }
                continue

            if 'variant' not in current_entry:
                if '[ClinVar]' in inner_text:
                    current_entry['variant'] = inner_text.replace(' [ClinVar]', '')
                else:
                    phenos = [pheno for pheno in inner_text.split(', INCLUDED') if pheno]
                    current_entry['phenotype_names'] += phenos
                continue

            # Rest of the entry will be the review

            # Extract the PubMed references from the text
            if 'pubmed' not in current_entry:
                current_entry['pubmeds_summary'] = {}

            for anchor in td.select('a.entry-reference'):
                current_entry['pubmeds_summary'][anchor.text] = anchor.get('pmid')

            # Extract the linked phenotype MIM IDs from the text
            if 'phenotype_ids' not in current_entry:
                current_entry['phenotype_ids'] = []

            omim_links = [anchor for anchor in td.select('a')
                          if anchor.get('href', '').startswith('/entry/')]
            for anchor in omim_links:
                current_entry['phenotype_ids'].append(anchor.text)

            # Extract the linked phenotypes acronyms from the text
            if 'phenotype_symbols' not in current_entry:
                current_entry['phenotype_symbols'] = []

            pheno_symbols = re.findall(r'\((\w+); \d+\)', td.text)
            current_entry['phenotype_symbols'] += pheno_symbols

            # Get the review text itself without HTML elements
            def extract_review_texts(element):
                texts = []
                for child in element.children:
                    if child.name == 'div' and 'change' in child['class']:
                        # Nested div.change with the review texts
                        texts += extract_review_texts(child)
                    elif child.name == 'br':
                        texts.append('\n')
                    else:
                        try:
                            texts.append(child.text)
                        except AttributeError:
                            texts.append(child)

                return texts

            texts = ''.join(extract_review_texts(td))

            if 'review' not in current_entry:
                current_entry['review'] = texts
                continue

            current_entry['review'] += '\n\n' + texts

        for entry in entries:
            entry['omim_id'] = omim_id
            entry['gene_name'] = gene_name
            entry['gene_symbol'] = gene_symbol

        return [entry for entry in entries if 'review' in entry]

