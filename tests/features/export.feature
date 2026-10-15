Feature: Export the researched content (US 7.1)
  As a user of the content enricher
  I want to save the original, enriched and translated content choosing the format and the name
  So that I get a document ready to consult

  Scenario Outline: Export the three contents in the chosen format
    Given an article about "Agujero negro" with enriched and translated content
    When I export it as "<format>" with the name "apuntes"
    Then the file "apuntes.<extension>" is created
    And the file can be opened and contains the three contents

    Examples:
      | format | extension |
      | TXT    | txt       |
      | PDF    | pdf       |

  Scenario Outline: Missing contents are marked as not available
    Given an article about "Agujero negro" without enriched or translated content
    When I export it as "<format>" with the name "apuntes"
    Then the missing contents are marked as not available

    Examples:
      | format |
      | TXT    |
      | PDF    |

  Scenario: The file cannot be saved
    Given an article about "Agujero negro" with enriched and translated content
    And the destination cannot be written
    When I try to export it as "PDF" with the name "apuntes"
    Then an ExportError is raised

  Scenario: Unsupported format
    Given an article about "Agujero negro" with enriched and translated content
    When I try to export it as "DOCX" with the name "apuntes"
    Then a ValueError is raised

  Scenario Outline: Invalid file names are rejected
    When the user types the file name "<name>"
    Then the file name is rejected

    Examples:
      | name   |
      | notas? |
      | a/b    |
      | CON    |
      | fin.   |
