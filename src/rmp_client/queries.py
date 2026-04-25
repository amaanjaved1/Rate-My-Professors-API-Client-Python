"""GraphQL query strings sent to the RateMyProfessors API.

Each constant matches an operation the RMP frontend uses. Variable names
and fragment names are kept identical so the server accepts them.
"""

RATINGS_LIST_QUERY = """
query RatingsListQuery($count: Int!, $id: ID!, $courseFilter: String, $cursor: String) {
  node(id: $id) {
    __typename
    ... on Teacher {
      ...RatingsList_teacher_4pguUW
      id
    }
  }
}
fragment RatingsList_teacher_4pguUW on Teacher {
  id
  legacyId
  firstName
  lastName
  department
  avgRating
  avgDifficulty
  numRatings
  wouldTakeAgainPercent
  school {
    id
    legacyId
    name
    city
    state
    country
    avgRating
    numRatings
  }
  ratings(first: $count, after: $cursor, courseFilter: $courseFilter) {
    edges {
      cursor
      node {
        id
        __typename
        comment
        helpfulRating
        clarityRating
        difficultyRating
        ratingTags
        date
        class
        grade
        attendanceMandatory
        textbookUse
        isForCredit
        thumbsUpTotal
        thumbsDownTotal
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

SCHOOL_RATINGS_LIST_QUERY = """
query SchoolRatingsListQuery($count: Int!, $id: ID!, $cursor: String) {
  node(id: $id) {
    ... on School {
      id
      legacyId
      name
      city
      state
      country
      numRatings
      avgRatingRounded
      summary {
        campusCondition
        campusLocation
        careerOpportunities
        clubAndEventActivities
        foodQuality
        internetSpeed
        schoolReputation
        schoolSafety
        schoolSatisfaction
        socialActivities
      }
      ratings(first: $count, after: $cursor) {
        edges {
          cursor
          node {
            id
            comment
            date
            reputationRating
            locationRating
            safetyRating
            socialRating
            opportunitiesRating
            happinessRating
            facilitiesRating
            internetRating
            foodRating
            clubsRating
            thumbsUpTotal
            thumbsDownTotal
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

SCHOOL_SEARCH_RESULTS_QUERY = """
query SchoolSearchResultsPageQuery($query: SchoolSearchQuery!, $count: Int!, $cursor: String) {
  search: newSearch {
    schools(query: $query, first: $count, after: $cursor) {
      edges {
        cursor
        node {
          id
          legacyId
          name
          city
          state
          numRatings
          avgRating
          avgRatingRounded
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      resultCount
    }
  }
}
"""

TEACHER_SEARCH_RESULTS_QUERY = """
query TeacherSearchResultsPageQuery($query: TeacherSearchQuery!, $count: Int!, $cursor: String) {
  search: newSearch {
    teachers(query: $query, first: $count, after: $cursor) {
      edges {
        cursor
        node {
          id
          legacyId
          firstName
          lastName
          avgRating
          numRatings
          wouldTakeAgainPercent
          avgDifficulty
          department
          school {
            id
            legacyId
            name
            city
            state
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      resultCount
    }
  }
}
"""

