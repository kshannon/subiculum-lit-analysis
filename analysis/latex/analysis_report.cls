\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{analysis_report}[2025/12/06 Analysis Report Class]

\LoadClass[11pt,letterpaper]{article}

\RequirePackage[margin=1in]{geometry}
\RequirePackage{times}
\RequirePackage{graphicx}
\RequirePackage{amsmath,amssymb}
\RequirePackage{booktabs}
\RequirePackage{caption}
\RequirePackage{subcaption}
\RequirePackage{hyperref}
\RequirePackage{xcolor}
\RequirePackage{fancyhdr}
\RequirePackage{titlesec}
\RequirePackage{enumitem}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=cyan,
    citecolor=blue,
}

\captionsetup{
    font=small,
    labelfont=bf,
    margin=10pt
}

\titleformat{\section}
    {\normalfont\Large\bfseries}{\thesection}{1em}{}
\titleformat{\subsection}
    {\normalfont\large\bfseries}{\thesubsection}{1em}{}
\titleformat{\subsubsection}
    {\normalfont\normalsize\bfseries}{\thesubsubsection}{1em}{}

\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\fancyhead[L]{\leftmark}
\fancyhead[R]{\thepage}
\fancyfoot[C]{}

\newcommand{\reporttitle}[1]{\def\@reporttitle{#1}}
\newcommand{\reportauthor}[1]{\def\@reportauthor{#1}}
\newcommand{\reportdate}[1]{\def\@reportdate{#1}}
\newcommand{\reportaffiliation}[1]{\def\@reportaffiliation{#1}}

\renewcommand{\maketitle}{
    \begin{center}
        {\LARGE\bfseries\@reporttitle\par}
        \vspace{0.5cm}
        {\large\@reportauthor\par}
        \vspace{0.2cm}
        {\normalsize\@reportaffiliation\par}
        \vspace{0.2cm}
        {\normalsize\@reportdate\par}
        \vspace{0.8cm}
    \end{center}
}

\endinput
