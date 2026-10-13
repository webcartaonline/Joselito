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
