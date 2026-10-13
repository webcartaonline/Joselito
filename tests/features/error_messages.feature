Feature: Clear messages when something fails (US 8.4)
  As a user of the content enricher
  I want to receive clear and understandable messages when something fails
  So that I understand what happened and what to do next

  Scenario: There is no internet connection (CA1)
    Given there is no internet connection
    When I research "Python"
    Then I see the message "No he podido conectar con Wikipedia"
    And I do not see any technical error
    And the application ends in a controlled way

  Scenario: Wikipedia takes too long to respond (CA2)
    Given Wikipedia takes too long to respond
    When I research "Python"
    Then I see the message "Wikipedia está tardando demasiado en responder"
    And I do not see any technical error
    And the application ends in a controlled way

  Scenario: The AI takes too long to respond (CA2)
    Given the AI takes too long to respond
    When I research "Python"
    Then I see the message "La IA está tardando demasiado en responder"
    And I do not see any technical error
    And the application finishes normally

  Scenario Outline: An empty or too long topic is asked again (CA3)
    When I type the topic "<topic>" and then "Python"
    Then I see the message "<message>"
    And Wikipedia only receives the topic "Python"
    And the application finishes normally

    Examples:
      | topic      | message                       |
      |            | No has escrito nada           |
      | (301 x)    | El tema es demasiado largo    |

  Scenario Outline: An empty or invalid language is asked again (CA3)
    When I type the language "<language>" and then "inglés"
    Then I see the message "<message>"
    And the application finishes normally

    Examples:
      | language | message                  |
      |          | No has escrito nada      |
      | 123      | no es un idioma válido   |

  Scenario: An unexpected error does not close the app abruptly (CA4)
    Given an unexpected error happens while searching
    When I research "Python"
    Then I see the message "Ha ocurrido un error inesperado"
    And I do not see any technical error
    And the application ends in a controlled way

  Scenario: The user cancels with Ctrl+C (CA4)
    Given the user presses Ctrl+C while searching
    When I research "Python"
    Then I see the message "Has cancelado la investigación"
    And I do not see any technical error
    And the application ends in a controlled way

  Scenario: The AI returns a broken answer (CA4)
    Given the AI returns a broken answer
    When I research "Python"
    Then I see the message "No he podido enriquecer el texto con IA"
    And I do not see any technical error
    And the application finishes normally
