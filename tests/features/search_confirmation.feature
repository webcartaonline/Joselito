Feature: Confirm the Wikipedia result before using it
  As a user of the content enricher
  I want to see the first result with its summary and confirm it, or choose another one
  So that a misspelled topic does not bring me an article I did not want

  Scenario: The first result is what the user was looking for
    Given Wikipedia finds "Árbol" with the summary "Un árbol es una planta."
    When I search "Alboles" and answer "Y"
    Then I see the first result "Árbol"
    And I see the summary "Un árbol es una planta."
    And the article "Árbol" is downloaded only once

  Scenario: Wikipedia offers no summary
    Given Wikipedia finds "Árbol" without a summary
    When I search "Alboles" and answer "Y"
    Then I see the first result "Árbol"
    And I see the summary "(Wikipedia no cuenta con una descripción de este artículo)"

  Scenario: Nothing is enriched until the user confirms
    Given Wikipedia finds 6 results about trees
    When I search "Alboles" and answer "N"
    Then nothing is enriched

  Scenario: The user picks another result by its number
    Given Wikipedia finds 6 results about trees
    When I search "Alboles" and answer "N 3"
    Then I see the other 5 results numbered from 1 to 5
    And I see the option 6 to write the topic again
    And the article "Árbol genealógico" is downloaded only once
    And only the chosen article is enriched

  Scenario: None of the results is the right one
    Given Wikipedia finds 6 results about trees
    When I search "Alboles" and answer "N 6 Árboles Y"
    Then Wikipedia is searched for "Alboles" and then for "Árboles"
