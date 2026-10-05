Feature: Wikipedia article scraping
  As a user of the content enricher
  I want to retrieve the title and first paragraphs of a Wikipedia article
  So that the content can be enriched, translated and exported

  Scenario: Fetch an existing article
    Given Wikipedia has an article about "Python"
    When I fetch the article for the topic "Python"
    Then I receive the article title
    And I receive at most 5 paragraphs

  Scenario: Topic with no search results
    Given Wikipedia has no results for "zzzxxyy"
    When I fetch the article for the topic "zzzxxyy"
    Then a ResourceNotFoundError is raised

  Scenario: Wikipedia does not respond in time
    Given Wikipedia exceeds the configured timeout
    When I fetch the article for the topic "Python"
    Then a ProviderTimeoutError is raised

  Scenario: Network failure
    Given there is no network connection
    When I fetch the article for the topic "Python"
    Then a WikiEnrichmentError is raised
