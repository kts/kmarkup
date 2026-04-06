"""
"""
def gen_tests():
    """
    """

    triples = [

 ("basic",
 "{x y}",
 [{"tag":"x",
   "children":["y"]}]
   ),

 ("basic",
 "{x A full sentence.}",
 [{"tag":"x",
   "children":["A full sentence."]}]
   ),

 ("nested",
 "{x A full {foo sentence}.}",
 [{"tag":"x",
   "children":[
      "A full ",
	  {"tag":"foo", "children":["sentence"]},
	  ".",]}
   ),

#more...

]
    
