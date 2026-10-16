Feature: Enrich the researched article with AI
  As a user of the content enricher
  I want the article enriched with AI-generated text
  So that I get more than the original Wikipedia content

  Scenario: The AI enriches the article (CA1)
    Given the AI works
    When I research "Python" responding "Y, N, N"
    Then I see the message "Texto enriquecido con IA"
    And the application finishes normally
