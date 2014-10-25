pystata
=======

Tools for controlling Stata from Python. Reads log files, generates dynamically customizable tables (in cpblTables format) from regression output; other tools



There are three repostories

pystata
cpbl-tables
cpblUtilities

now populated on my github page (cpbl) which, along with a file 
cpblDefaults.py (a version of which is in pystata) make a minimal set of 
stuff to run the pystata-demo.py program in pystata repository.

As you will see, making this code open is a big step because it's a decade 
of personalized kludges, with some very useful tools interspersed. :)

Here's the idea of one component of pystata, the latexRegressionClass:

I write regression commands like in a do file, but with some extra 
annotation. E.g. lines like the following could preceed a regression call

*name:Full model
*flag:state dummies
*flag:cluster=household

and these give some control over annotation in output tables.

Preprocessing of the stata commands by my class adds numerous extra 
features to the eventual Stata log file (such as eliciting the covariance 
table).  Stata code in multiline text format such as the above is 
converted into a models data structure in python, and the estimate results 
appear in this structure when they're available.

Sets of estimates are grouped together into tables, and the stata code 
collected by the class. At some point, this code is executed as a batch 
Stata job.

The model estimates are available for plotting or further analysis in 
python, including in Pandas format,  and are also used to generate LaTeX 
tables of results.

There is much customization of these tables possible, including 
substituting Stata variable names for LaTeX markup, specification of 
ordering of variables, and so on, which can be refined without waiting for 
the estimates to be rerun.

The LaTeX tables are stored individuall, each in a custom format .tex file 
which actually includes, as comments for posterity, the entire Stata log 
file lines for the relevant estimates.

These .tex files are incorporated into LaTeX articles, beamer 
presentations, or etc, using the cpbl-tables style files, and they allow 
on-the-fly reformatting into various kinds of tables, such as wide, long, 
landscape, etc, simply by changing the call function in your main 
document. By adding "transpose" to the name, you can even invoke a 
transposed version of the table.


That is the gist of what the pystata-demo.py is supposed to show, and of 
course there are many other things in each of the packages.

I'm sure you'll have lots of fiddling to even get stuff set up at first; I 
hope it's manageable and worthwhile.

The hope is to sort out the idiosyncratic from the useful/general, and the good from the old/bad.
