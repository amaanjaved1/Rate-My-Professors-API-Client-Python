from rmp_client import RMPClient


def main() -> None:
    with RMPClient() as client:
        result = client.search_professors("Smith", page_size=10)
        for prof in result.professors:
            print(f"{prof.name} ({prof.department}) - rating={prof.overall_rating}")


if __name__ == "__main__":
    main()

