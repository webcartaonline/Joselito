Feature: Brief summary of the enriched article
  As a user of the content enricher
  I want an optional brief summary of the enriched text
  So that I can grasp the content at a glance

  Scenario: The user accepts the brief summary (CA1)
    Given the summarizer works
    When I research "Python" responding "Y, Y, N"
    Then I see the message "Resumen breve de Python"
    And the application finishes normally

  Scenario: The user declines the brief summary
    Given the summarizer works
    When I research "Python" responding "Y, N, N"
    Then I do not see the message "Resumen breve de Python"
    And the application finishes normally

  Scenario: The summary fails (CA2)
    Given the summarizer fails
    When I research "Python" responding "Y, Y, N"
    Then I see the message "No he podido generar el resumen breve"
    And the application finishes normally

  Scenario: No summary is offered without enriched text (CA2)
    Given the AI fails
    When I research "Python" responding "Y, N"
    Then I do not see the message "¿Quieres un resumen breve? (Y/N)"
    And the application finishes normally
