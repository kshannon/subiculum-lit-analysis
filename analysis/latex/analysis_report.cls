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
\RequirePackage{etoolbox}

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
\titlespacing*{\section}{0pt}{12pt plus 2pt minus 2pt}{6pt plus 1pt minus 1pt}
\titleformat{\subsection}
    {\normalfont\large\bfseries}{\thesubsection}{1em}{}
\titlespacing*{\subsection}{0pt}{10pt plus 2pt minus 2pt}{4pt plus 1pt minus 1pt}
\titleformat{\subsubsection}
    {\normalfont\normalsize\bfseries}{\thesubsubsection}{1em}{}
\titlespacing*{\subsubsection}{0pt}{8pt plus 2pt minus 2pt}{4pt plus 1pt minus 1pt}

\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\setlength{\headheight}{14pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\floatsep}{10pt plus 2pt minus 2pt}
\setlength{\intextsep}{10pt plus 2pt minus 2pt}

\setlist{itemsep=2pt,parsep=0pt,topsep=4pt,partopsep=0pt}

\renewcommand{\topfraction}{0.85}
\renewcommand{\bottomfraction}{0.85}
\renewcommand{\textfraction}{0.10}
\renewcommand{\floatpagefraction}{0.75}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyhead[R]{\small\thepage}
\fancyfoot[C]{}

\newcommand{\reporttitle}[1]{\def\@reporttitle{#1}}
\newcommand{\reportauthor}[1]{\def\@reportauthor{#1}}
\newcommand{\reportdate}[1]{\def\@reportdate{#1}}
\newcommand{\reportaffiliation}[1]{\def\@reportaffiliation{#1}}

\renewcommand{\maketitle}{
    \thispagestyle{empty}
    \begin{flushleft}
        {\LARGE\bfseries\@reporttitle\par}
        \vspace{1em}
        {\large\@reportauthor\par}
        \ifdef{\@reportaffiliation}{%
            \vspace{0.3em}
            {\normalsize\@reportaffiliation\par}
        }{}
        \vspace{0.3em}
        {\normalsize\textit{\@reportdate}\par}
        \vspace{1.5em}
    \end{flushleft}
}

\endinput
