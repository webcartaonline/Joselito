Feature: Translate the article with Google Translate
  As a user of the content enricher
  I want the article translated to the language I choose
  So that I can read it in my own language

  Scenario: The article is translated (CA1)
    Given the translator works
    When I research "Python" responding "Y, N, N"
    Then I see the message "Traducción al inglés"
    And the application finishes normally

  Scenario: The translator takes too long (CA2)
    Given the translator is slow
    When I research "Python" responding "Y, N, N"
    Then I see the message "Google Translate ha tardado demasiado"
    And the application ends in a controlled way

  Scenario: The translator fails (CA2)
    Given the translator fails
    When I research "Python" responding "Y, N, N"
    Then I see the message "No he podido traducir el contenido con Google Translate"
    And the application ends in a controlled way
