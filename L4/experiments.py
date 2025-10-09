import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import sqlite3 as sqll
    import natasha as nlp
    import numpy as np
    import plotly.express as px
    return mo, nlp, pd, px, sqll


@app.cell
def _(pd, sqll):
    con = sqll.connect("L2/reviews.db")
    df = pd.read_sql_query("SELECT * FROM reviews", con)
    df
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""В таблице есть пустые значения, но конкретно в интересующих нас колонках (review_descr, stars) - отсутствуют пустые значения""")
    return


@app.cell
def _(df):
    df_f = df

    df_f["review_descr_token_count"] = df_f["review_descr"].apply(
        lambda x: len(x.split())
    )

    df_f
    return (df_f,)


@app.cell
def _(df_f):
    df_f.describe()
    return


@app.cell
def _(px):
    def plot_histogram(df, column):
        fig = px.histogram(df, x=column, title=f"Гистограмма по столбцу {column}")
        return fig
    return (plot_histogram,)


@app.cell
def _(df_f, plot_histogram):
    plot_histogram(df_f, "stars")
    return


@app.cell
def _(df_f, plot_histogram):
    plot_histogram(df_f, "review_descr_token_count")
    return


@app.cell
def _(df_f, plot_histogram):
    plot_histogram(df_f, "likes")
    return


@app.cell
def _(df_f, plot_histogram):
    plot_histogram(df_f, "comments")
    return


@app.cell
def _(df_f):
    def find_outliers_iqr(df, column):
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers = df[(df[column] < lower_bound) | (df[column] > upper_bound)]
        return outliers


    print(f"stars: {len(find_outliers_iqr(df_f, 'stars'))}")
    print(f"year usage: {len(find_outliers_iqr(df_f, 'year_usage'))}")
    print(f"likes: {len(find_outliers_iqr(df_f, 'likes'))}")
    print(f"comments: {len(find_outliers_iqr(df_f, 'comments'))}")
    print(
        f"descr length: {len(find_outliers_iqr(df_f, 'review_descr_token_count'))}"
    )
    return


@app.cell
def _(df_f):
    def filter_and_sort(df, max_words):
        filtered_df = df[df["review_descr_token_count"] <= max_words]
        return filtered_df.sort_values(
            by="review_descr_token_count", ascending=False
        )


    filter_and_sort(df_f, 100)
    return


@app.function
def filter_and_sort_custom(df, col, min_v, max_v):
    filtered_df = df[df[col] <= max_v and df[col] >= min_v]
    return filtered_df.sort_values(by=col)


@app.cell
def _(df_f):
    def using_biterator():
        import sys
        sys.path.append('./')
        import L4.iter as biter
        lcounts = []
        bter = biter.bi_directional_iterator(df_f["review_descr_token_count"])
        while True:
            try:
                lcounts.append(next(bter))
                lcounts.append(bter.prev())
                next(bter)
                lcounts.append(next(bter))
            except:
                break
        return lcounts
    using_biterator()
    return


@app.cell
def _(df_f, nlp):
    def _():
        import nltk.corpus
        import string
        import razdel
        import collections
    
        segmenter = nlp.Segmenter()
        morph_vocab = nlp.MorphVocab()
        emb = nlp.NewsEmbedding()
        morph_tagger = nlp.NewsMorphTagger(emb)
    
        RUSSIAN_STOPWORDS = set(nltk.corpus.stopwords.words('russian'))
        PUNCTUATION = set(string.punctuation)
        ADDITIONAL_NOISE = {' ', '«', '»', '—', '–', '...', '``', "''", '`', "'", '„', '“', '”'}
        FILTERS = RUSSIAN_STOPWORDS.union(PUNCTUATION).union(ADDITIONAL_NOISE)

        def preprocess_text_natasha(text):
        
            tokens = [t.text.lower() for t in razdel.tokenize(text)]
        
            doc = nlp.Doc(' '.join(tokens))
            doc.segment(segmenter)
        
            doc.tag_morph(morph_tagger)
        
            for token in doc.tokens:
                token.lemmatize(morph_vocab)
    
            lemmas = []
            for token in doc.tokens:
                lemma = token.lemma

                is_word_allowed = lemma not in FILTERS
                is_not_number = not lemma.isdigit()
                is_long_enough = len(lemma) > 2
            
                if is_word_allowed and is_not_number and is_long_enough:
                    lemmas.append(lemma)
                
            return lemmas

        def get_word_counts(df, col):        
            lems = df[col].apply(preprocess_text_natasha)
            all_tokens = [item for sublist in lems for item in sublist]

            word_counts = collections.Counter(all_tokens)

            return word_counts
    
        return get_word_counts(df_f, "title")
    counter = _()
    return (counter,)


@app.cell
def _(counter):
    counter.most_common(10)
    return


@app.cell
def _(counter, px):
    commons = counter.most_common(10)
    x = [item1 for item1, item2 in commons]
    y = [item2 for item1, item2 in commons]
    px.bar(x=x, y=y, title="Топ 10 слов").update_layout(xaxis_title="Слово", yaxis_title="Количество")
    return


if __name__ == "__main__":
    app.run()
