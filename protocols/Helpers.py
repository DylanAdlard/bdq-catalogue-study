import pandas as pd
from Bio import SeqIO
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from protocols.Predict import predict
from protocols import Helpers


DNA_Codons = {
    # 'M' - START, '_' - STOP
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "TGT": "C",
    "TGC": "C",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "TTT": "F",
    "TTC": "F",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
    "CAT": "H",
    "CAC": "H",
    "ATA": "I",
    "ATT": "I",
    "ATC": "I",
    "AAA": "K",
    "AAG": "K",
    "TTA": "L",
    "TTG": "L",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "ATG": "M",
    "AAT": "N",
    "AAC": "N",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAA": "Q",
    "CAG": "Q",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "AGA": "R",
    "AGG": "R",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "AGT": "S",
    "AGC": "S",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "TGG": "W",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "!",
    "TAG": "!",
    "TGA": "!",
}


def parse_vcf(vcf_file, gene, database):
    index = 0
    Dict = {}
    with open(vcf_file, "r") as f:
        for line in f:
            if line[0] != "#":
                line = line.split("\t")
                line[0] = line[0].split("/")
                if database == "shaheed":
                    line[0][5] = line[0][5].split(".")
                    uniqueid = line[0][5][0:8]
                elif database == "CRyPTIC1":
                    line[0][6] = line[0][6].split(".")
                    uniqueid = line[0][6][0:8]

                uniqueid = "".join([i + "." for i in uniqueid])[:-1]
                variant = line[1]
                line[-1] = line[-1].split(":")
                if database == "shaheed":
                    FRS = line[-1][3]
                    RRS = line[-1][2].split(",")
                elif database == "CRyPTIC1":
                    FRS = line[-1][4]
                    RRS = line[-1][3].split(",")
                mutation = "".join(line[3:5])
                ref = line[3]
                alt = line[4]
                print(alt)

                Dict[index] = {
                    "UNIQUEID": uniqueid,
                    "GENE": gene,
                    "GENOME_INDEX": int(variant),
                    "GENETIC_REF": ref,
                    "GENETIC_ALT": alt,
                    "MUTATION": mutation,
                    "RRS_vcf": RRS,
                    "FRS_vcf": FRS,
                }
                index += 1

    df = pd.DataFrame.from_dict(Dict)

    return df


def mic_to_float(arr):
    float_mic = []
    for i in arr:
        try:
            float_mic.append(float(i))
        except ValueError:
            try:
                float_mic.append(float(i[1:]))
            except ValueError:
                float_mic.append(float(i[2:]))

    return float_mic


def DNA_mut_to_aa(vcf_df, genes):
    """genes must be a dictionary with complement bool as values"""

    vcf_df = shift_genome_index(vcf_df, genes)

    mut_products = []
    for i in vcf_df.index:
        for gene in genes.keys():
            if vcf_df["GENE"][i] == gene:
                if len(vcf_df["GENETIC_MUTATION"][i]) > 2:
                    mut_products.append(str(vcf_df["PRODUCT_POSITION"][i]) + "_indel")
                else:
                    codon = extract_codons(gene, genes[gene])[1][
                        int(vcf_df["PRODUCT_POSITION"][i])
                    ]
                    pos_in_codon = vcf_df["GENOME_INDEX_SHIFTED"][i] % 3
                    codon[pos_in_codon] = vcf_df["GENETIC_MUTATION"][i][-1]
                    mut_products.append(
                        str(vcf_df["MUTATION"][i][:-1] + DNA_Codons["".join(codon)])
                    )

    vcf_df["MUTATION"] = mut_products
    return vcf_df


def shift_genome_index(vcf_df, genes):
    """genes must be a dictionary with complement bool as values"""

    genome_index_shifted = []
    for i in vcf_df.index:
        for gene in genes.keys():
            if vcf_df["GENE"][i] == gene:
                if genes[gene]:
                    genome_index_shifted.append(
                        np.max(extract_codons(gene, genes[gene])[0])
                        - vcf_df["GENOME_INDEX"][i]
                    )  # range is for the complement strand (the gene is 'backwards')
                else:
                    genome_index_shifted.append(
                        vcf_df["GENOME_INDEX"][i]
                        - np.min(extract_codons(gene, genes[gene])[0])
                    )

    vcf_df["GENOME_INDEX_SHIFTED"] = genome_index_shifted

    return vcf_df


def extract_codons(gene, complement=False):
    for record in SeqIO.parse(f"../../Data/genetic/{gene}.fasta", "fasta"):
        record = record

    try:
        idx_range = [int(i) for i in record.id.split(":")[1].split("-")]
    except ValueError:
        idx_range = [
            int(i[1:]) for i in record.id.split(":")[1].split("-")
        ]  # may have a 'c' before the number

    complements = {"A": "T", "T": "A", "C": "G", "G": "C"}
    if complement:
        seq = ""
        for i in record.seq:
            seq += complements[i]
        seq = [i for i in seq]
    else:
        seq = [i for i in record.seq]

    codons = []
    for i in range(0, len(seq), 3):
        codons.append(seq[i : i + 3])

    return idx_range, codons


def RSIsolateTable(df, genes):
    """returns df of number of isolates that contain each parameter"""
    table = {}
    table["Total"] = {
        "R": df[df.PHENOTYPE == "R"].UNIQUEID.nunique(),
        "S": df[df.PHENOTYPE == "S"].UNIQUEID.nunique(),
        "Total": df.UNIQUEID.nunique(),
    }
    for i in genes:
        d = df[df.GENE == i]
        table[i] = {
            "R": d[d.PHENOTYPE == "R"].UNIQUEID.nunique(),
            "S": d[d.PHENOTYPE == "S"].UNIQUEID.nunique(),
            "Total": d[d.PHENOTYPE == "R"].UNIQUEID.nunique()
            + d[d.PHENOTYPE == "S"].UNIQUEID.nunique(),
        }

    return pd.DataFrame.from_dict(table).T


def RSVariantTable(df, genes):
    table = {}
    table["Total"] = {
        "R": df[df.PHENOTYPE == "R"].UNIQUEID.count(),
        "S": df[df.PHENOTYPE == "S"].UNIQUEID.count(),
        "Total": df.UNIQUEID.count(),
    }
    for i in genes:
        d = df[df.GENE == i]
        table[i] = {
            "R": d[d.PHENOTYPE == "R"].UNIQUEID.count(),
            "S": d[d.PHENOTYPE == "S"].UNIQUEID.count(),
            "Total": d[d.PHENOTYPE == "R"].UNIQUEID.count()
            + d[d.PHENOTYPE == "S"].UNIQUEID.count(),
        }

    return pd.DataFrame.from_dict(table).T


def extract_solos(gene, df):
    solos, solo_ids = {}, []
    id_list = df.UNIQUEID.unique().tolist()
    for i in id_list:
        id_only = df[df.UNIQUEID == i]
        if (id_only.MUTATION.nunique() == 1) & (id_only.GENE.tolist()[0] == gene):
            solo_ids.append(i)
            if id_only.MUTATION.tolist()[0] in solos.keys():
                solos[id_only.MUTATION.tolist()[0]].append(
                    id_only.METHOD_MIC.tolist()[0]
                )
            else:
                solos[id_only.MUTATION.tolist()[0]] = id_only.METHOD_MIC.tolist()

    return solos, solo_ids


def extract_mics(gene, df, hz_thresh=3, output_counts=False, solo_ids=None):
    mut_counts = df[["GENE", "MUTATION"]].value_counts().reset_index(name="count")
    if output_counts:
        print(mut_counts)

    mic_dict = {}
    for i in mut_counts[
        (mut_counts["count"] >= hz_thresh) & (mut_counts.GENE == gene)
    ].index:
        mic_dict[mut_counts["MUTATION"][i]] = df[
            (df.GENE == gene)
            & (df.MUTATION == mut_counts["MUTATION"][i])
            & (~df.UNIQUEID.isin(solo_ids))
        ].METHOD_MIC.tolist()

    return mic_dict


def order_x(target_x, x):
    """Orders a second axis of discrete values relative to the first.
    Inserts blanks if that x value is unmatched"""

    ordered_x = {}
    no_overlap = {}
    for k in target_x.keys():
        if k in x.keys():
            ordered_x[k] = x[k]
        else:
            ordered_x[k] = []

    for k in x.keys():
        if k not in ordered_x.keys():
            ordered_x[k] = x[k]

    return ordered_x


def tabulate(mic_dict, solo_dict, solo_ids, df, y_axis_keys, ecoff, minor=False):
    """this can only be run on an mic_dict that has passed through mutation_mic_plot()
    due to y axis mappings.
    Could have also calculate these values by fancy indexing the dfs"""
    var_r, var_s = 0, 0
    for dict in (mic_dict, solo_dict):
        # if dict == mic_dict:

        for v in dict.values():
            for mic in v:
                if float(mic) > y_axis_keys[ecoff]:
                    var_r += 1
                else:
                    var_s += 1
        if dict == solo_dict:
            solo_r, solo_s = 0, 0
            for v in dict.values():
                for mic in v:
                    if float(mic) > y_axis_keys[ecoff]:
                        solo_r += 1
                    else:
                        solo_s += 1

    minor_r, minor_s = 0, 0
    if not minor:
        for id in solo_ids:
            if df[df.UNIQUEID == id].MUTATION.nunique() > 1:
                if float(df[df.UNIQUEID == id].MIC_FLOAT.unique().tolist()[0]) > 1.0:
                    minor_r += 1
                else:
                    minor_s += 1

    table = {
        "variants": {"R": var_r, "S": var_s},
        "solos": {"R": solo_r, "S": solo_s},
        "minor": {"R": minor_r, "S": minor_s},
    }

    return pd.DataFrame.from_dict(table).T


def plot_catalogue_counts(all, catalogue):
    sns.set_context("notebook")

    genes_S, genes_R = [], []
    for i in catalogue[catalogue.phenotype == "S"].index:
        gene = all[all.GENE_MUT == catalogue["GENE_MUT"][i]].GENE.tolist()[0]
        genes_S.append(gene)
    for i in catalogue[catalogue.phenotype == "R"].index:
        gene = all[all.GENE_MUT == catalogue["GENE_MUT"][i]].GENE.tolist()[0]
        genes_R.append(gene)
    plt.figure(figsize=(7, 5))
    df = pd.concat(
        axis=0,
        ignore_index=True,
        objs=[
            pd.DataFrame.from_dict({"Gene": genes_S, "phenotype": "S"}),
            pd.DataFrame.from_dict({"Gene": genes_R, "phenotype": "R"}),
        ],
    ).sort_values(["Gene"], ascending=True, key=lambda col: col.str.lower())
    fig, ax = plt.subplots()
    sns.histplot(
        data=df, x="Gene", hue="phenotype", multiple="dodge", ax=ax, discrete=True
    )
    plt.ylabel("Number of Catalogued Mutations")

