Feature: Clear messages when something fails (US 8.4)
  As a user of the content enricher
  I want to receive clear and understandable messages when something fails
  So that I understand what happened and what to do next

  Scenario: There is no internet connection, even after retrying (CA1)
    Given there is no internet connection
    When I research "Python" answering "Y, Y"
    Then I see the message "No he podido conectar con Wikipedia (intento 1 de 3)"
    And I see the message "No he podido conectar con Wikipedia después de 3 intentos"
    And Wikipedia was asked 3 times
    And I do not see any technical error
    And the application ends in a controlled way

  Scenario: The connection comes back after retrying (CA1)
    Given the connection fails once and then works
    When I research "Python" answering "Y, Y, N"
    Then I see the message "intento 1 de 3"
    And the application finishes normally

  Scenario: The user decides not to retry (CA1)
    Given there is no internet connection
    When I research "Python" answering "N"
    Then I see the message "De acuerdo, no lo vuelvo a intentar"
    And the application ends in a controlled way

  Scenario: Wikipedia asks to wait before retrying (CA2)
    Given Wikipedia asks to wait 5 seconds and then works
    And the user presses a key during the countdown
    When I research "Python" answering "Y, Y, N"
    Then I see the message "Wikipedia ha recibido demasiadas peticiones"
    And I see the message "Paciencia, si no Wikipedia bloqueará esta IP"
    And the countdown lasted 5 seconds
    And the application finishes normally

  Scenario: Wikipedia is slow once (CA2)
    Given Wikipedia is slow once and then works
    When I research "Python" answering "Y, N"
    Then I see the message "Wikipedia está tardando demasiado. Lo intento otra vez..."
    And the application finishes normally

  Scenario: Wikipedia keeps being slow (CA2)
    Given Wikipedia takes too long to respond
    When I research "Python" answering "Python lenguaje"
    Then I see the message "Prueba a escribir el tema de otra manera"
    And I see the message "Wikipedia no está respondiendo a tiempo"
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
