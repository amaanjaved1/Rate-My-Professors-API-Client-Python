from rmp_client import RMPClient


def main() -> None:
    professor_id = "PROFESSOR_ID"

    with RMPClient() as client:
        professor = client.get_professor(professor_id)
        print(professor)


if __name__ == "__main__":
    main()

